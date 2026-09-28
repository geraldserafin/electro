/// <reference lib="webworker" />
// Python (Pyodide) runs here, off the main thread, so the page stays responsive.
import type { PyodideAPI } from "pyodide";

const PYODIDE = "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/";

type Request =
  | { id: number; type: "init"; bundleUrl: string }
  | { id: number; type: "run"; code: string; schematics: string }
  | { id: number; type: "code"; schematic: string; name: string }
  | { id: number; type: "fromCode"; source: string; name: string; old: string }
  | { id: number; type: "simulate"; schematic: string }
  | { id: number; type: "reset" };

interface Kernel {
  run(code: string, schematics: string): string;
  code(schematic: string, name: string): string;
  from_code(source: string, name: string, old: string): string;
  simulate(schematic: string): string;
  reset(): void;
}

let kernel: Promise<Kernel> | null = null;

async function start(bundleUrl: string): Promise<Kernel> {
  const { loadPyodide } = await import(/* @vite-ignore */ `${PYODIDE}pyodide.mjs`);
  const py: PyodideAPI = await loadPyodide({ indexURL: PYODIDE });
  await py.loadPackage(["sympy"]);
  // no-cache: after the Python sources change, a reload must not get the old bundle
  const bundle: Record<string, string> = await (await fetch(bundleUrl, { cache: "no-cache" })).json();
  for (const [path, source] of Object.entries(bundle)) {
    const full = `/home/pyodide/lib/${path}`;
    py.FS.mkdirTree(full.slice(0, full.lastIndexOf("/")));
    py.FS.writeFile(full, source);
  }
  py.runPython("import sys; sys.path.insert(0, '/home/pyodide/lib')");
  return py.pyimport("electro_notebook.kernel") as unknown as Kernel;
}

self.onmessage = async (event: MessageEvent<Request>) => {
  const request = event.data;
  try {
    if (request.type === "init") {
      kernel = start(request.bundleUrl);
      await kernel;
      self.postMessage({ id: request.id, ok: true, result: null });
      return;
    }
    if (!kernel) throw new Error("The kernel was not started (init first).");
    const k = await kernel;
    const result =
      request.type === "run" ? k.run(request.code, request.schematics)
      : request.type === "code" ? k.code(request.schematic, request.name)
      : request.type === "fromCode" ? k.from_code(request.source, request.name, request.old)
      : request.type === "simulate" ? k.simulate(request.schematic)
      : (k.reset(), null);
    self.postMessage({ id: request.id, ok: true, result });
  } catch (error) {
    self.postMessage({ id: request.id, ok: false, error: String(error) });
  }
};
