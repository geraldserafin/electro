// The page's handle on the compiler worker: every call a message and a promise. The worker starts
// only when asked (an Arduino or a Pico on a board), and then fetches the compiler once (tens of MB,
// cached), and each board's sysroot the first time.
import { type Progress, report } from "@/features/downloads/store";
import type { Board, Compiled } from "./toolchain";

export type { Board, Compiled };

type Reply = { id: number; ok: true; result: unknown } | { id: number; ok: false; error: string };

class Compiler {
  private worker: Worker | null = null;
  private pending = new Map<number, { resolve: (v: unknown) => void; reject: (e: Error) => void }>();
  private nextId = 1;
  private loading: Partial<Record<Board, Promise<void>>> = {};

  private call(type: string, payload: object = {}): Promise<unknown> {
    if (!this.worker) {
      this.worker = new Worker(new URL("./worker.ts", import.meta.url), { type: "module" });
      this.worker.onmessage = (event: MessageEvent<Reply | { progress: Progress }>) => {
        if ("progress" in event.data) return report(event.data.progress);
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

  /** Fetch the compiler for ``board`` ahead of the first sketch (a note with one was opened). */
  load(board: Board): Promise<void> {
    return (this.loading[board] ??= this.call("load", { board })
      .then(() => undefined)
      .catch((e) => {
        delete this.loading[board];
        throw e;
      }));
  }

  /** A sketch → the board's program (an Uno's Intel HEX, a Pico's flash image), or what the compiler said. */
  async compile(sketch: string, board: Board): Promise<Compiled> {
    return (await this.call("compile", { sketch, board })) as Compiled;
  }
}

export const compiler = new Compiler();
