// The examples' sketches compiled ahead (src/features/simulation/compiler/prebuilt.ts): each Uno's and
// Pico's sketch in examples/*/*.electro.json, by the page's own compiler (public/arduino/, read from
// disk as toolchain.test.ts does), into public/arduino/built/<key>.hex|.bin, and the keys into
// prebuilt.json. Run after changing an example's sketch or the compiler: pnpm prebuild-sketches.
import { mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { fileOf, keyOf } from "../src/features/simulation/compiler/prebuilt";
import { type Board, compile, toolchain } from "../src/features/simulation/compiler/toolchain";

// (as firmware.ts: a text whose first line names a file is a program given whole)
const firmwareFile = (text: string) => /^\s*\/\/\s*firmware:/.test(text.split("\n").find((l) => l.trim()) ?? "");

const dir = new URL("../public/arduino/", import.meta.url);
const out = new URL("built/", dir);
const read = (name: string) => readFileSync(new URL(name, dir));
const buffer = (b: Buffer) => b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength) as ArrayBuffer;

/** Every board's sketch in an example (not a program given whole: its file). */
function sketches(): { board: Board; sketch: string; where: string }[] {
  const found: { board: Board; sketch: string; where: string }[] = [];
  const examples = new URL("../examples/", import.meta.url);
  for (const course of readdirSync(examples, { withFileTypes: true }).filter((d) => d.isDirectory()))
    for (const name of readdirSync(new URL(`${course.name}/`, examples)).filter((n) => n.endsWith(".electro.json"))) {
      const visit = (value: unknown): void => {
        if (Array.isArray(value)) {
          value.forEach(visit);
          return;
        }
        if (!value || typeof value !== "object") return;
        const { kind, text } = value as { kind?: unknown; text?: unknown };
        if ((kind === "arduino" || kind === "pico") && typeof text === "string" && text.trim() && !firmwareFile(text))
          found.push({ board: kind === "pico" ? "pico" : "uno", sketch: text, where: `${course.name}/${name}` });
        Object.values(value).forEach(visit);
      };
      visit(JSON.parse(readFileSync(new URL(`${course.name}/${name}`, examples), "utf8")));
    }
  return found;
}

const { modules: names } = JSON.parse(read("llvm.json").toString()) as { modules: string[] };
const { instantiate } = await import(new URL("llvm.js", dir).href);
const modules = Object.fromEntries(
  await Promise.all(names.map(async (n) => [n, await WebAssembly.compile(read(n))] as const)),
);
const chains = {
  uno: await toolchain(
    { instantiate, modules, clangHeaders: buffer(read("clang-headers.tar")), sysroot: buffer(read("sysroot.tar")) },
    "uno",
  ),
  pico: await toolchain(
    { instantiate, modules, clangHeaders: buffer(read("clang-headers.tar")), sysroot: buffer(read("pico.tar")) },
    "pico",
  ),
};

rmSync(out, { recursive: true, force: true });
mkdirSync(out, { recursive: true });
const keys = new Set<string>();
let failed = false;
for (const { board, sketch, where } of sketches()) {
  const key = await keyOf(board, sketch);
  if (keys.has(key)) continue;
  const result = await compile(chains[board], sketch);
  if ("hex" in result) writeFileSync(new URL(fileOf(board, key), out), result.hex);
  else if ("image" in result) writeFileSync(new URL(fileOf(board, key), out), result.image);
  else {
    console.error(`${where}: ${JSON.stringify(result)}`);
    failed = true;
    continue;
  }
  keys.add(key);
  console.log(`${where}: ${fileOf(board, key)}`);
}
writeFileSync(
  new URL("../src/features/simulation/compiler/prebuilt.json", import.meta.url),
  `${JSON.stringify([...keys].sort(), null, 2)}\n`,
);
process.exit(failed ? 1 : 0);
