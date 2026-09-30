// The page's handle on the Typst worker: started when first needed, then kept (the compiler and
// the fonts load once). Every document is an answer to wait for.
import { type Progress, report } from "@/features/downloads/store";
import type { TypstDocument } from "./document";
import type { Reply, Request } from "./protocol";

export type Compiled = Extract<Reply, { ok: true }> | Extract<Reply, { ok: false }>;

let worker: Worker | null = null;
let next = 0;
const waiting = new Map<number, (reply: Reply) => void>();

function start(): Worker {
  if (worker) return worker;
  worker = new Worker(new URL("./worker.ts", import.meta.url), { type: "module" });
  worker.onmessage = ({ data }: MessageEvent<Reply | { progress: Progress }>) => {
    if ("progress" in data) return report(data.progress);
    waiting.get(data.id)?.(data);
    waiting.delete(data.id);
  };
  return worker;
}

const send = (request: Request) => start().postMessage(request);

/** Load Typst ahead of the first document (it is some megabytes). */
export const warmUp = () => send({ type: "warm" });

export function compile(document: TypstDocument): Promise<Compiled> {
  const id = ++next;
  return new Promise((resolve) => {
    waiting.set(id, resolve);
    send({ type: "compile", id, document });
  });
}

/**
 * Load Typst ahead, when the browser has nothing else to do (while the note is open, before anyone
 * exports) — the first export then shows its pages at once. Not on a metered connection ("save
 * data"): there it waits for the dialog. Returns: cancel (the note closed first).
 */
export function warmUpWhenIdle(): () => void {
  if (worker || (navigator as { connection?: { saveData?: boolean } }).connection?.saveData) return () => {};
  if ("requestIdleCallback" in window) {
    const handle = window.requestIdleCallback(warmUp, { timeout: 15_000 });
    return () => window.cancelIdleCallback(handle);
  }
  const timer = setTimeout(warmUp, 3000); // (Safari: no idle callbacks)
  return () => clearTimeout(timer);
}
