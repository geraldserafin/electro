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
  | { id: number; type: "run"; code: string; schematics: string; standard: string }
  | { id: number; type: "code"; schematic: string; name: string }
  | { id: number; type: "fromCode"; source: string; name: string; old: string }
  | { id: number; type: "simulate"; schematic: string }
  | { id: number; type: "live"; problem: string }
  | { id: number; type: "frequency"; schematic: string }
  | { id: number; type: "sweep"; schematic: string; element: string; lo: string; hi: string }
  | { id: number; type: "spread"; schematic: string; tol: number }
  | { id: number; type: "taskValues"; schematic: string; steps: string }
  | { id: number; type: "fromDrawing"; drawing: string; strict: boolean }
  | { id: number; type: "renderSvg"; schematic: string }
  | { id: number; type: "netlistOf"; schematic: string }
  | { id: number; type: "reset" };

interface Kernel {
  run(code: string, schematics: string, standard: string): string;
  code(schematic: string, name: string): string;
  from_code(source: string, name: string, old: string): string;
  simulate(schematic: string): string;
  live(problem: string): string;
  frequency(schematic: string): string;
  sweep_plot(schematic: string, element: string, lo: string, hi: string): string;
  spread(schematic: string, tol: number): string;
  task_values(schematic: string, steps: string): string;
  from_drawing(drawing: string, strict: boolean): string;
  render_svg(schematic: string): string;
  netlist_of(schematic: string): string;
  reset(): void;
}

// electro.sim.simulate() runs its steps here, in JavaScript, when there is this (js.electroSim):
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
      request.type === "run"
        ? k.run(request.code, request.schematics, request.standard)
        : request.type === "code"
          ? k.code(request.schematic, request.name)
          : request.type === "fromCode"
            ? k.from_code(request.source, request.name, request.old)
            : request.type === "simulate"
              ? k.simulate(request.schematic)
              : request.type === "live"
                ? k.live(request.problem)
                : request.type === "frequency"
                  ? k.frequency(request.schematic)
                  : request.type === "sweep"
                    ? k.sweep_plot(request.schematic, request.element, request.lo, request.hi)
                    : request.type === "spread"
                      ? k.spread(request.schematic, request.tol)
                      : request.type === "taskValues"
                        ? k.task_values(request.schematic, request.steps)
                        : request.type === "fromDrawing"
                          ? k.from_drawing(request.drawing, request.strict)
                          : request.type === "renderSvg"
                            ? k.render_svg(request.schematic)
                            : request.type === "netlistOf"
                              ? k.netlist_of(request.schematic)
                              : (k.reset(), null);
    self.postMessage({ id: request.id, ok: true, result });
  } catch (error) {
    self.postMessage({ id: request.id, ok: false, error: String(error) });
  }
};
