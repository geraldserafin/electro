// The page's handle on the Python worker: every call is a message and a promise.

import { type Progress, report } from "@/features/downloads/store";
import type { LiveCircuit } from "@/features/simulation/engine";
import type { Failure } from "@/shared/model/issues";
import type { ElementResult, Output, Problem, SchematicData } from "@/shared/model/types";

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
  async simulate(schematic: SchematicData): Promise<{ results: Record<string, ElementResult>; problems: Problem[] }> {
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

  async reset(): Promise<void> {
    await this.call("reset");
  }
}

export const kernel = new Kernel();
