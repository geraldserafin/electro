/// <reference lib="webworker" />
// Python (Pyodide) runs here, off the main thread, so the page stays responsive.
import type { PyodideAPI } from "pyodide";
import { runProgram } from "@/features/simulation/engine";
import { trackDownloads } from "@/shared/lib/trackDownloads";

// everything it fetches (Pyodide, its packages, our Python) shown on the page as it comes
trackDownloads(() => "python");

const PYODIDE = "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/";

type Request =
  | { id: number; type: "init"; bundleUrl: string }
  | { id: number; type: "run"; code: string; problems: string; units: string; apart?: boolean }
  | { id: number; type: "fromCode"; source: string; name: string }
  | { id: number; type: "solve"; problem: string }
  | { id: number; type: "live"; problem: string }
  | { id: number; type: "frequency"; problem: string }
  | { id: number; type: "sweep"; problem: string; element: string; lo: string; hi: string }
  | { id: number; type: "spread"; problem: string; tol: number }
  | { id: number; type: "taskValues"; problem: string; steps: string }
  | { id: number; type: "reset" }
  | { id: number; type: "file"; name: string; bytes: Uint8Array }; // a note's file, into the working directory

interface Kernel {
  run(code: string, problems: string, units: string, apart?: boolean): string;
  from_code(source: string, name: string): string;
  solve(problem: string): string;
  live(problem: string): string;
  frequency(problem: string): string;
  sweep_plot(problem: string, element: string, lo: string, hi: string): string;
  spread(problem: string, tol: number): string;
  task_values(problem: string, steps: string): string;
  reset(): void;
}

// electro.simulate() runs its steps here, in JavaScript, when there is this (js.electroSim):
// the same loop as its own, many times faster than in Pyodide
type PyList = { toJs(): [number, number][]; destroy?(): void };
(self as unknown as { electroSim: unknown }).electroSim = {
  run: (json: string, tEnd: number, dtMax: number, schedule: ((t: number) => PyList) | null) =>
    runProgram(
      json,
      tEnd,
      dtMax,
      schedule &&
        ((t: number) => {
          const list = schedule(t);
          const pairs = list.toJs();
          list.destroy?.();
          return pairs;
        }),
    ),
};

let kernel: Promise<Kernel> | null = null;
let pyodide: PyodideAPI | null = null;

async function start(bundleUrl: string): Promise<Kernel> {
  const { loadPyodide } = await import(/* @vite-ignore */ `${PYODIDE}pyodide.mjs`);
  const py: PyodideAPI = (pyodide = await loadPyodide({ indexURL: PYODIDE }));
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

// a cell's packages before it runs: what it imports that Pyodide has built (numpy, scipy, matplotlib, pandas…),
// and what its `%pip install …` lines name, from PyPI (micropip: pure Python wheels, or Pyodide's own)
const PIP = /^[ \t]*[%!]pip[ \t]+install[ \t]+(.*)$/gm;
const quiet = { messageCallback: () => {} };

async function packages(py: PyodideAPI, code: string): Promise<{ code: string; outputs: object[] }> {
  const wanted = [...code.matchAll(PIP)]
    .flatMap((m) => m[1].trim().split(/\s+/))
    .filter((a) => a && !a.startsWith("-"));
  const rest = code.replace(PIP, ""); // (the line stays, empty: the errors' line numbers stay right)
  const outputs: object[] = [];
  if (wanted.length) {
    try {
      await py.loadPackage("micropip", quiet);
      await py.pyimport("micropip").install(wanted);
      outputs.push({ type: "stream", data: `Successfully installed ${wanted.join(" ")}\n` });
    } catch (error) {
      const lines = String(error).trim().split("\n");
      outputs.push({ type: "error", data: `pip install ${wanted.join(" ")}: ${lines[lines.length - 1]}` });
    }
  }
  try {
    await py.loadPackagesFromImports(rest, quiet);
  } catch {
    // (not to be had: its import says so, as the cell runs)
  }
  return { code: rest, outputs };
}

async function run(k: Kernel, request: Extract<Request, { type: "run" }>): Promise<string> {
  const { code, outputs } = await packages(pyodide!, request.code);
  const result = k.run(code, request.problems, request.units, request.apart ?? false);
  return outputs.length ? JSON.stringify([...outputs, ...JSON.parse(result)]) : result;
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
    if (request.type === "file") {
      pyodide!.FS.writeFile(request.name, request.bytes); // (the working directory: /home/pyodide)
      self.postMessage({ id: request.id, ok: true, result: null });
      return;
    }
    const result =
      request.type === "run"
        ? await run(k, request)
        : request.type === "fromCode"
          ? k.from_code(request.source, request.name)
          : request.type === "solve"
            ? k.solve(request.problem)
            : request.type === "live"
              ? k.live(request.problem)
              : request.type === "frequency"
                ? k.frequency(request.problem)
                : request.type === "sweep"
                  ? k.sweep_plot(request.problem, request.element, request.lo, request.hi)
                  : request.type === "spread"
                    ? k.spread(request.problem, request.tol)
                    : request.type === "taskValues"
                      ? k.task_values(request.problem, request.steps)
                      : (k.reset(), null);
    self.postMessage({ id: request.id, ok: true, result });
  } catch (error) {
    self.postMessage({ id: request.id, ok: false, error: String(error) });
  }
};
