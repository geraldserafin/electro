// Compiling an Arduino sketch with clang and lld for AVR, built as one WebAssembly program
// (scripts/build-llvm-wasm.sh, make-arduino-compiler.sh), run by YoWASP's WASI runtime on a virtual
// file system that holds the sysroot (scripts/make-arduino-sysroot.sh: avr-libc, the Arduino core
// and libraries, prebuilt). The sketch is the only thing compiled; the rest is linked in.
// No browser here: worker.ts fetches the files, arduino-compiler.test.ts reads them from disk.
import { Application, Exit, type Tree } from "@yowasp/runtime";
import { prepareSketch } from "@electro/notes-api";
import { parseTar } from "nanotar";

const LIBRARIES = ["SPI", "Wire", "EEPROM", "SoftwareSerial", "Servo"];
const FLASH = 32256; // bytes of an Uno's flash the bootloader leaves

/** The same flags make-arduino-sysroot.sh built the core and the libraries with. */
const FLAGS = [
  "--target=avr", "-mmcu=atmega328p", "-Os", "-ffunction-sections", "-fdata-sections", "-fno-color-diagnostics",
  "-DF_CPU=16000000L", "-DARDUINO=10607", "-DARDUINO_AVR_UNO", "-DARDUINO_ARCH_AVR",
  '-D__ATTR_PROGMEM__=__attribute__((__section__(".progmem.data")))', // clang ignores __progmem__
  "-nostdlibinc", "-isystem", "/arduino/include", "-I/arduino/core", ...LIBRARIES.map((l) => `-I/arduino/libraries/${l}`),
  "-std=gnu++11", "-fno-exceptions", "-fno-threadsafe-statics", "-fno-rtti", "-w",
];

const LINK = [
  "--gc-sections", "-T", "/arduino/avr5.x",
  "--defsym=__DATA_REGION_ORIGIN__=0x800100", "--defsym=__TEXT_REGION_LENGTH__=32768", "--defsym=__DATA_REGION_LENGTH__=2048",
  "/arduino/lib/crtatmega328p.o", "sketch.o",
  "--start-group", ...LIBRARIES.filter((l) => l !== "EEPROM").map((l) => `/arduino/lib/lib${l}.a`), "/arduino/lib/core.a",
  "/arduino/lib/libm.a", "/arduino/lib/libc.a", "/arduino/lib/libatmega328p.a", "/arduino/lib/libgcc.a", "--end-group",
];

export type Compiled = { hex: string; size: number } | { failed: string } | { tooBig: number; flash: number };

/** What make-arduino-compiler.sh and make-arduino-sysroot.sh made: the program's instantiate()
 *  (from llvm.js), its WebAssembly modules, and the two tar files. */
export interface Parts {
  instantiate: unknown;
  modules: Record<string, WebAssembly.Module>;
  clangHeaders: ArrayBuffer;
  sysroot: ArrayBuffer;
}

function tree(buffer: ArrayBuffer): Tree {
  const root: Tree = {};
  for (const entry of parseTar(buffer)) {
    const parts = entry.name.replace(/^\.\//, "").split("/").filter(Boolean);
    if (!parts.length) continue;
    let dir = root;
    for (const part of parts.slice(0, -1)) dir = (dir[part] ??= {}) as Tree;
    const last = parts[parts.length - 1];
    if (entry.type === "directory") dir[last] ??= {};
    else dir[last] = entry.data ?? new Uint8Array();
  }
  return root;
}

/** The compiler, ready to run: its files on the virtual file system, the modules compiled. */
export async function toolchain(parts: Parts): Promise<Application> {
  const filesystem = { usr: tree(parts.clangHeaders), arduino: tree(parts.sysroot) };
  const resources = { modules: async () => parts.modules, filesystem: async () => filesystem, totalSize: 0 };
  // the runtime awaits what it is given here: a resource module ({modules, filesystem}), whatever its .d.ts says
  const app = new Application(resources as unknown as () => Promise<unknown>, parts.instantiate, "llvm");
  await app.run(); // take the resources now, not on the first sketch
  return app;
}

/** Run one of the tools: the files after it, what it said (stdout and stderr together, as text)
 *  and its stdout alone. */
async function run(app: Application, args: string[], files: Tree) {
  let output = "", stdout = "";
  const decoder = new TextDecoder(), out = new TextDecoder();
  const both = (bytes: Uint8Array | null) => { if (bytes) output += decoder.decode(bytes, { stream: true }); };
  const only = (bytes: Uint8Array | null) => { if (bytes) { stdout += out.decode(bytes, { stream: true }); both(bytes); } };
  try {
    const after = (await app.run(args, files, { stdout: only, stderr: both, decodeASCII: false })) as Tree;
    return { files: after, output, stdout, ok: true };
  } catch (e) {
    if (e instanceof Exit) return { files: e.files, output, stdout, ok: false };
    throw e;
  }
}

/** Clang's driver cannot start its own compiler here (no processes): ask it what it would run
 *  (-###) and run that, in the same program. */
async function clang(app: Application, args: string[], files: Tree) {
  const plan = await run(app, ["clang", "-###", ...args], files);
  if (!plan.ok) return plan;
  const jobs = plan.output.split("\n").filter((l) => l.startsWith(' "'))
    .map((l) => Array.from(l.matchAll(/ (?:([^ "]+)|"((?:[^"\\]|\\.)*)")/g), (m) => m[1] ?? m[2].replace(/\\(.)/g, "$1")));
  let current = files;
  // each job: the program's path (empty here), then the tool in the multi-call program ("clang", "-cc1", …)
  for (const [, ...rest] of jobs) {
    const step = await run(app, rest, current);
    if (!step.ok) return step;
    current = step.files;
  }
  return { files: current, stdout: "", output: plan.output.split("\n").filter((l) => !l.startsWith(' "') && !/^(clang|Target|Thread|InstalledDir|Build config)/.test(l)).join("\n"), ok: true };
}

/** Bytes of program in an Intel HEX file. */
const hexSize = (hex: string) =>
  hex.split(/\r?\n/).filter((l) => l.startsWith(":") && l.slice(7, 9) === "00").reduce((n, l) => n + parseInt(l.slice(1, 3), 16), 0);

export async function compile(app: Application, sketch: string): Promise<Compiled> {
  const compiled = await clang(app, [...FLAGS, "-c", "sketch.cpp", "-o", "sketch.o"], { "sketch.cpp": prepareSketch(sketch) });
  if (!compiled.ok) return { failed: compiled.output.trim() };
  const linked = await run(app, ["ld.lld", "-o", "sketch.elf", ...LINK], compiled.files);
  if (!linked.ok) return { failed: linked.output.replaceAll("/arduino/lib/", "").trim() };
  // to stdout: writing a file, objcopy renames a temporary one, which the runtime cannot do
  const hexed = await run(app, ["llvm-objcopy", "-O", "ihex", "-R", ".eeprom", "sketch.elf", "-"], linked.files);
  if (!hexed.ok) return { failed: hexed.output.trim() };
  const hex = hexed.stdout;
  const size = hexSize(hex);
  if (size > FLASH) return { tooBig: size, flash: FLASH };
  return { hex, size };
}

