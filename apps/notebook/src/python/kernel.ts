// The page's handle on the Python worker: every call is a message and a promise.
import type { ElementResult, Output, SchematicData } from "../types";

type Reply = { id: number; ok: true; result: unknown } | { id: number; ok: false; error: string };

class Kernel {
  private worker = new Worker(new URL("./worker.ts", import.meta.url), { type: "module" });
  private pending = new Map<number, { resolve: (v: unknown) => void; reject: (e: Error) => void }>();
  private nextId = 1;
  readonly ready: Promise<void>;

  constructor() {
    this.worker.onmessage = (event: MessageEvent<Reply>) => {
      const reply = event.data;
      const call = this.pending.get(reply.id);
      if (!call) return;
      this.pending.delete(reply.id);
      if (reply.ok) call.resolve(reply.result);
      else call.reject(new Error(reply.error));
    };
    const bundleUrl = new URL("py/bundle.json", document.baseURI).href;
    this.ready = this.call("init", { bundleUrl }).then(() => undefined);
  }

  private call(type: string, payload: object = {}): Promise<unknown> {
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.worker.postMessage({ id, type, ...payload });
    });
  }

  async run(code: string, schematics: Record<string, SchematicData>): Promise<Output[]> {
    const text = (await this.call("run", { code, schematics: JSON.stringify(
      Object.fromEntries(Object.entries(schematics).map(([name, s]) => [name, JSON.stringify(s)])),
    ) })) as string;
    return JSON.parse(text);
  }

  /** The drawing as plain electro code (`+`/`|` when possible, else `net(...)`). */
  async code(schematic: SchematicData, name: string): Promise<string> {
    return (await this.call("code", { schematic: JSON.stringify(schematic), name })) as string;
  }

  /** Code edited in a schematic's code view, laid out back into a drawing (or the error in it). */
  async fromCode(source: string, name: string, old: SchematicData):
    Promise<{ schematic: SchematicData } | { error: string }> {
    return JSON.parse((await this.call("fromCode", { source, name, old: JSON.stringify(old) })) as string);
  }

  /** The "Symuluj" button: every element's values, plus a table / warnings for under the drawing. */
  async simulate(schematic: SchematicData, data: string):
    Promise<{ results: Record<string, ElementResult>; outputs: Output[] }> {
    return JSON.parse((await this.call("simulate", { schematic: JSON.stringify(schematic), data })) as string);
  }

  async reset(): Promise<void> {
    await this.call("reset");
  }
}

export const kernel = new Kernel();
