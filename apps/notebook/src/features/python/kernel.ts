// The page's handle on the Python worker: every call is a message and a promise.

import { type Progress, report } from "@/features/downloads/store";
import { bodeSvg, histogramSvg, traceSvg } from "@/features/plots/svg";
import { drawingFromCode } from "@/features/schematic/fromCode";
import { library, libraryFor } from "@/features/schematic/library";
import { isComponent, key, pins } from "@/features/schematic/model";
import { withParts } from "@/features/schematic/parts";
import { elementsOf, problemOf, solveData } from "@/features/schematic/problem";
import type { LiveCircuit } from "@/features/simulation/engine";
import type { Failure } from "@/shared/model/issues";
import type { ElementResult, Output, Problem, SchematicData, SymbolStandard } from "@/shared/model/types";
import { given, shown } from "./outputs";

type Reply = { id: number; ok: true; result: unknown } | { id: number; ok: false; error: string };

class Kernel {
  private worker = new Worker(new URL("./worker.ts", import.meta.url), { type: "module" });
  private pending = new Map<number, { resolve: (v: unknown) => void; reject: (e: Error) => void }>();
  private nextId = 1;
  readonly ready: Promise<void>;

  constructor() {
    this.worker.onmessage = (event: MessageEvent<Reply | { progress: Progress }>) => {
      if ("progress" in event.data) return report(event.data.progress);
      const reply = event.data;
      const call = this.pending.get(reply.id);
      if (!call) return;
      this.pending.delete(reply.id);
      if (reply.ok) call.resolve(reply.result);
      else call.reject(new Error(reply.error));
    };
    // from the app's root, not the page's address (/notes/:id would put it under /notes/)
    const bundleUrl = new URL(`${import.meta.env.BASE_URL}py/bundle.json`, location.origin).href;
    this.ready = this.call("init", { bundleUrl }).then(() => undefined);
  }

  private call(type: string, payload: object = {}): Promise<unknown> {
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.worker.postMessage({ id, type, ...payload });
    });
  }

  /** A code cell, the schematic cells' problems as its variables; what it shows drawn with `standard`'s
   *  symbols (the note's). */
  async run(
    code: string,
    schematics: Record<string, SchematicData>,
    standard: SymbolStandard = "iec",
  ): Promise<Output[]> {
    const text = (await this.call("run", { code, ...given(schematics, library) })) as string;
    return shown(JSON.parse(text), libraryFor(standard));
  }

  /** Code edited in a schematic's code view, laid out back into a drawing (or the error in it). */
  async fromCode(
    source: string,
    name: string,
    old: SchematicData,
  ): Promise<{ schematic: SchematicData } | { error: Failure }> {
    const back = JSON.parse((await this.call("fromCode", { source, name })) as string);
    return "error" in back ? back : drawingFromCode(back, old, library);
  }

  /** A schematic cell's run button: every element's values, each mark's, what is sought (``sought.ts``),
   *  and what went wrong. */
  async solve(schematic: SchematicData): Promise<{
    results: Record<string, ElementResult>;
    problems: Problem[];
    found?: Record<string, string | null>;
  }> {
    try {
      const problem = JSON.stringify(solveData(schematic, library));
      return JSON.parse((await this.call("solve", { problem })) as string);
    } catch (error) {
      return { results: {}, problems: [{ kind: "error", text: String(error) }] };
    }
  }

  /** A schematic cell's play button: the drawing compiled for the live simulation (or the error in it),
   *  and which point each of its wires and pins is on. */
  async live(schematic: SchematicData): Promise<LiveCircuit | { error: Failure }> {
    const { elements, names } = elementsOf(schematic, library);
    const reply = JSON.parse((await this.call("live", { problem: JSON.stringify({ elements }) })) as string);
    if ("error" in reply) return reply;
    const at = (p: [number, number]) => names.get(key(p)) ?? null;
    const lib = withParts(library, schematic.parts);
    return {
      program: reply.program,
      wires: schematic.wires.map((w) => at(w.points[0])),
      pins: Object.fromEntries(
        schematic.elements.filter((e) => isComponent(e.kind)).map((e) => [e.id, pins(e, lib).map(at)]),
      ),
    };
  }

  /** A schematic cell's frequency button: the Bode plot of the drawing (or the error in it). */
  async frequency(schematic: SchematicData): Promise<{ svg: string } | { error: Failure }> {
    const reply = JSON.parse((await this.call("frequency", { problem: this.problem(schematic) })) as string);
    return "error" in reply ? reply : { svg: bodeSvg(reply.bode) };
  }

  /** An element's sweep (its inspector): the outputs as its value goes from ``lo`` to ``hi``. */
  async sweep(
    schematic: SchematicData,
    element: string,
    lo: string,
    hi: string,
  ): Promise<{ svg: string } | { error: Failure }> {
    const reply = JSON.parse(
      (await this.call("sweep", { problem: this.problem(schematic), element, lo, hi })) as string,
    );
    return "error" in reply ? reply : { svg: traceSvg(reply.trace) };
  }

  /** The tolerance button: the outputs over many builds, each R, C and L within ``tol``. */
  async spread(schematic: SchematicData, tol: number): Promise<{ svg: string } | { error: Failure }> {
    const reply = JSON.parse((await this.call("spread", { problem: this.problem(schematic), tol })) as string);
    return "error" in reply ? reply : { svg: histogramSvg(reply.histogram) };
  }

  /** The drawing's elements as a problem, for the plots. */
  private problem(schematic: SchematicData): string {
    return JSON.stringify({ elements: elementsOf(schematic, library).elements });
  }

  /** Quantities of the drawing as it is, its marks' data with it (``steps``: each an id and its
   *  expression, ``I_R1``): each one's number, or why it has none. */
  async taskValues(
    schematic: SchematicData,
    steps: { id: string; value: string }[],
  ): Promise<{ values: Record<string, { value: number } | { error: Failure }> } | { error: Failure }> {
    let problem: string;
    try {
      const { marks: _, ...data } = problemOf(schematic, library);
      problem = JSON.stringify(data);
    } catch (error) {
      return { error: { data: String(error) } };
    }
    const call = { problem, steps: JSON.stringify(steps.map(({ id, value }) => ({ id, value }))) };
    return JSON.parse((await this.call("taskValues", call)) as string);
  }

  async reset(): Promise<void> {
    await this.call("reset");
  }
}

export const kernel = new Kernel();
