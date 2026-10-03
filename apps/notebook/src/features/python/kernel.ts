// The page's handle on the Python worker: every call is a message and a promise.

import { type Progress, report } from "@/features/downloads/store";
import type { LiveCircuit } from "@/features/simulation/engine";
import type { Failure } from "@/shared/model/issues";
import type { ElementResult, Output, Problem, SchematicData } from "@/shared/model/types";

/** A circuit as data: its elements (kind as the schematic names them), each with its nodes in its
 *  terminals' order (``0``: ground). */
export type Netlist = {
  elements: {
    id: string;
    kind: string;
    value?: string | null;
    text?: string | null;
    nodes: string[];
    at?: [number, number][]; // a drawing's: where its terminals are (grid units), in the nodes' order
  }[];
  wires?: [number, number][][]; // a drawing's: its wires, as polylines
};

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

  /** A code cell; its schematics drawn with `standard`'s symbols (the note's). */
  async run(code: string, schematics: Record<string, SchematicData>, standard = "iec"): Promise<Output[]> {
    const text = (await this.call("run", {
      code,
      standard,
      schematics: JSON.stringify(
        Object.fromEntries(Object.entries(schematics).map(([name, s]) => [name, JSON.stringify(s)])),
      ),
    })) as string;
    return JSON.parse(text);
  }

  /** The drawing as plain electro code (`+`/`|` when possible, else `net(...)`). */
  async code(schematic: SchematicData, name: string): Promise<string> {
    return (await this.call("code", { schematic: JSON.stringify(schematic), name })) as string;
  }

  /** Code edited in a schematic's code view, laid out back into a drawing (or the error in it). */
  async fromCode(
    source: string,
    name: string,
    old: SchematicData,
  ): Promise<{ schematic: SchematicData } | { error: Failure }> {
    return JSON.parse((await this.call("fromCode", { source, name, old: JSON.stringify(old) })) as string);
  }

  /** A schematic cell's run button: every element's values, and what went wrong. */
  async simulate(schematic: SchematicData): Promise<{
    results: Record<string, ElementResult>;
    problems: Problem[];
    found?: Record<string, string | null>; // what ``find`` asks for, what it came to
  }> {
    return JSON.parse((await this.call("simulate", { schematic: JSON.stringify(schematic) })) as string);
  }

  /** A schematic cell's play button: the drawing compiled for the live simulation (or the error in it). */
  async live(schematic: SchematicData): Promise<LiveCircuit | { error: Failure }> {
    return JSON.parse((await this.call("live", { schematic: JSON.stringify(schematic) })) as string);
  }

  /** A schematic cell's frequency button: the Bode plot of the drawing (or the error in it). */
  async frequency(schematic: SchematicData): Promise<{ svg: string } | { error: Failure }> {
    return JSON.parse((await this.call("frequency", { schematic: JSON.stringify(schematic) })) as string);
  }

  /** An element's sweep (its inspector): the outputs as its value goes from ``lo`` to ``hi``. */
  async sweep(
    schematic: SchematicData,
    element: string,
    lo: string,
    hi: string,
  ): Promise<{ svg: string } | { error: Failure }> {
    return JSON.parse((await this.call("sweep", { schematic: JSON.stringify(schematic), element, lo, hi })) as string);
  }

  /** The tolerance button: the outputs over many builds, each R, C and L within ``tol``. */
  async spread(schematic: SchematicData, tol: number): Promise<{ svg: string } | { error: Failure }> {
    return JSON.parse((await this.call("spread", { schematic: JSON.stringify(schematic), tol })) as string);
  }

  /** Quantities of the drawing as it is (``steps``: each an id and its expression, ``I_R1``): each
   *  one's number, or why it has none. */
  async taskValues(
    schematic: SchematicData,
    steps: { id: string; value: string }[],
  ): Promise<{ values: Record<string, { value: number } | { error: Failure }> } | { error: Failure }> {
    const call = {
      schematic: JSON.stringify(schematic),
      steps: JSON.stringify(steps.map(({ id, value }) => ({ id, value }))),
    };
    return JSON.parse((await this.call("taskValues", call)) as string);
  }

  /** A circuit described as data and drawn as a picture has it (``at``, ``wires``): drawn so, or why
   *  not — its drawing joining other than its nodes say (``error.mismatch``). */
  async fromDrawing(
    drawing: Netlist,
    strict = false, // its wires joining otherwise: said (error.mismatch), not laid anew
  ): Promise<
    { schematic: SchematicData; rerouted: boolean } | { error: Failure & { mismatch?: string[]; dangling?: string[] } }
  > {
    return JSON.parse((await this.call("fromDrawing", { drawing: JSON.stringify(drawing), strict })) as string);
  }

  /** A drawing as a picture (SVG): to set beside the one it was read from. */
  async renderSvg(schematic: SchematicData): Promise<string> {
    return (await this.call("renderSvg", { schematic: JSON.stringify(schematic) })) as string;
  }

  /** A drawing as data (for an AI to read): its elements and their nodes. */
  async netlistOf(schematic: SchematicData): Promise<Netlist | { error: Failure }> {
    return JSON.parse((await this.call("netlistOf", { schematic: JSON.stringify(schematic) })) as string);
  }

  async reset(): Promise<void> {
    await this.call("reset");
  }
}

export const kernel = new Kernel();
