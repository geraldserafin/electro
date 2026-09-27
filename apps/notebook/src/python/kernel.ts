// The page's handle on the Python worker: every call is a message and a promise.
import type { Output, SchematicData, SymbolLibrary } from "../types";

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

  async symbols(): Promise<SymbolLibrary> {
    return JSON.parse((await this.call("symbols")) as string);
  }

  async run(code: string, schematics: Record<string, SchematicData>): Promise<Output[]> {
    const text = (await this.call("run", { code, schematics: JSON.stringify(
      Object.fromEntries(Object.entries(schematics).map(([name, s]) => [name, JSON.stringify(s)])),
    ) })) as string;
    return JSON.parse(text);
  }

  async reset(): Promise<void> {
    await this.call("reset");
  }
}

export const kernel = new Kernel();
