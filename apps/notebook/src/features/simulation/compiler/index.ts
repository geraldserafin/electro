// The page's handle on the compiler worker: every call a message and a promise. The worker starts
// only when asked (an Arduino on a board), and then fetches the compiler once (tens of MB, cached).
import type { Compiled } from "./toolchain";

export type { Compiled };

type Reply = { id: number; ok: true; result: unknown } | { id: number; ok: false; error: string };

class Compiler {
  private worker: Worker | null = null;
  private pending = new Map<number, { resolve: (v: unknown) => void; reject: (e: Error) => void }>();
  private nextId = 1;
  private loading: Promise<void> | null = null;

  private call(type: string, payload: object = {}): Promise<unknown> {
    if (!this.worker) {
      this.worker = new Worker(new URL("./worker.ts", import.meta.url), { type: "module" });
      this.worker.onmessage = (event: MessageEvent<Reply>) => {
        const call = this.pending.get(event.data.id);
        if (!call) return;
        this.pending.delete(event.data.id);
        if (event.data.ok) call.resolve(event.data.result);
        else call.reject(new Error(event.data.error));
      };
    }
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.worker!.postMessage({ id, type, ...payload });
    });
  }

  /** Fetch the compiler ahead of the first sketch (a note with an Arduino was opened). */
  load(): Promise<void> {
    return (this.loading ??= this.call("load").then(() => undefined).catch((e) => { this.loading = null; throw e; }));
  }

  /** A sketch → the Uno's program (Intel HEX), or what the compiler said. */
  async compile(sketch: string): Promise<Compiled> {
    return (await this.call("compile", { sketch })) as Compiled;
  }
}

export const compiler = new Compiler();
