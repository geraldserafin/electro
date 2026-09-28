/// <reference lib="webworker" />
// The in-page Arduino compiler (toolchain.ts), off the main thread: its files are fetched from
// public/arduino/ once, on the first "load" or "compile".
import type { Application } from "@yowasp/runtime";
import { compile, toolchain, type Compiled } from "./toolchain";

export type { Compiled };

const BASE = new URL(`${import.meta.env.BASE_URL}arduino/`, self.location.origin).href;

type Request = { id: number; type: "load" } | { id: number; type: "compile"; sketch: string };

async function fetchParts() {
  const manifest: { modules: string[] } = await (await fetch(`${BASE}llvm.json`)).json();
  const [{ instantiate }, modules, clangHeaders, sysroot] = await Promise.all([
    import(/* @vite-ignore */ `${BASE}llvm.js`),
    Promise.all(manifest.modules.map(async (name) => [name, await WebAssembly.compileStreaming(fetch(`${BASE}${name}`))] as const)),
    fetch(`${BASE}clang-headers.tar`).then((r) => r.arrayBuffer()),
    fetch(`${BASE}sysroot.tar`).then((r) => r.arrayBuffer()),
  ]);
  return { instantiate, modules: Object.fromEntries(modules), clangHeaders, sysroot };
}

let llvm: Promise<Application> | null = null;
const load = () => (llvm ??= fetchParts().then(toolchain));

self.onmessage = async (event: MessageEvent<Request>) => {
  const request = event.data;
  try {
    const result = request.type === "load" ? (await load(), null) : await compile(await load(), request.sketch);
    self.postMessage({ id: request.id, ok: true, result });
  } catch (error) {
    llvm = null; // try again next time (a failed download, say)
    self.postMessage({ id: request.id, ok: false, error: String(error) });
  }
};
