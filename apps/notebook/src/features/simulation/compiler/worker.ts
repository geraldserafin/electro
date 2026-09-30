/// <reference lib="webworker" />
// The in-page Arduino compiler (toolchain.ts), off the main thread: its files are fetched from
// public/arduino/ once — the program and clang's headers on the first "load" or "compile", a board's
// sysroot the first time that board is asked for (a Pico's is the larger one).
import { trackDownloads } from "@/shared/lib/trackDownloads";
import { type Board, type Compiled, compile, type Toolchain, toolchain } from "./toolchain";

// its files shown on the page as they come: the compiler, each board's libraries
trackDownloads((url) => (url.endsWith("sysroot.tar") ? "uno" : url.endsWith("pico.tar") ? "pico" : "compiler"));

export type { Compiled };

const BASE = new URL(`${import.meta.env.BASE_URL}arduino/`, self.location.origin).href;
const SYSROOT: Record<Board, string> = { uno: "sysroot.tar", pico: "pico.tar" };

type Request =
  | { id: number; type: "load"; board: Board }
  | { id: number; type: "compile"; board: Board; sketch: string };

async function fetchProgram() {
  const manifest: { modules: string[] } = await (await fetch(`${BASE}llvm.json`)).json();
  const [{ instantiate }, modules, clangHeaders] = await Promise.all([
    import(/* @vite-ignore */ `${BASE}llvm.js`),
    Promise.all(
      manifest.modules.map(
        async (name) => [name, await WebAssembly.compileStreaming(fetch(`${BASE}${name}`))] as const,
      ),
    ),
    fetch(`${BASE}clang-headers.tar`).then((r) => r.arrayBuffer()),
  ]);
  return { instantiate, modules: Object.fromEntries(modules), clangHeaders };
}

let program: ReturnType<typeof fetchProgram> | null = null;
const toolchains: Partial<Record<Board, Promise<Toolchain>>> = {};
const load = (board: Board) =>
  (toolchains[board] ??= (async () => {
    const [parts, sysroot] = await Promise.all([
      (program ??= fetchProgram()),
      fetch(`${BASE}${SYSROOT[board]}`).then((r) => {
        if (!r.ok) throw new Error(`${SYSROOT[board]}: HTTP ${r.status}`);
        return r.arrayBuffer();
      }),
    ]);
    return toolchain({ ...parts, sysroot }, board);
  })());

self.onmessage = async (event: MessageEvent<Request>) => {
  const request = event.data;
  try {
    const result =
      request.type === "load"
        ? (await load(request.board), null)
        : await compile(await load(request.board), request.sketch);
    self.postMessage({ id: request.id, ok: true, result });
  } catch (error) {
    // try again next time (a failed download, say)
    program = null;
    delete toolchains[request.board];
    self.postMessage({ id: request.id, ok: false, error: String(error) });
  }
};
