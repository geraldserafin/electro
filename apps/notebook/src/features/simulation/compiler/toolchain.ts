// Compiling an Arduino sketch with clang and lld for AVR, built as one WebAssembly program
// (scripts/build-llvm-wasm.sh, make-arduino-compiler.sh), run by YoWASP's WASI runtime on a virtual
// file system that holds the sysroot (scripts/make-arduino-sysroot.sh: avr-libc, the Arduino core
// and libraries, prebuilt). The sketch is the only thing compiled; the rest is linked in.
// No browser here: worker.ts fetches the files, arduino-compiler.test.ts reads them from disk.
import { Application, Exit, type Tree } from "@yowasp/runtime";
import { prepareSketch } from "@electro/notes-api";
import { parseTar } from "nanotar";

const LIBRARIES = ["SPI", "Wire", "EEPROM", "SoftwareSerial", "Servo", "LiquidCrystal", "LiquidCrystal_I2C", "Adafruit_BusIO",
  "Adafruit_GFX", "Adafruit_SSD1306", "RTClib"];
const FLASH = 32256; // bytes of an Uno's flash the bootloader leaves

/** The same flags make-arduino-sysroot.sh built the core and the libraries with. */
const FLAGS = [
  "--target=avr", "-mmcu=atmega328p", "-Os", "-ffunction-sections", "-fdata-sections", "-fno-color-diagnostics",
  "-DF_CPU=16000000L", "-DARDUINO=10607", "-DARDUINO_AVR_UNO", "-DARDUINO_ARCH_AVR",
  '-D__ATTR_PROGMEM__=__attribute__((__section__(".progmem.data")))', // clang ignores __progmem__
  "-D__HAS_DELAY_CYCLES=0", // util/delay.h: not GCC's __builtin_avr_delay_cycles, which clang has not got
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

/** Run one of the tools: the files after it, what it said (stderr, and stdout unless ``binary``, as
 *  text), its stdout as text, and — ``binary`` — as bytes (an object file). */
async function run(app: Application, args: string[], files: Tree, binary = false) {
  let output = "", stdout = "";
  const chunks: Uint8Array[] = [];
  const decoder = new TextDecoder(), out = new TextDecoder();
  const both = (bytes: Uint8Array | null) => { if (bytes) output += decoder.decode(bytes, { stream: true }); };
  const only = (bytes: Uint8Array | null) => {
    if (!bytes) return;
    if (binary) chunks.push(bytes.slice());
    else { stdout += out.decode(bytes, { stream: true }); both(bytes); }
  };
  const bytes = () => {
    const all = new Uint8Array(chunks.reduce((n, c) => n + c.length, 0));
    chunks.reduce((at, c) => (all.set(c, at), at + c.length), 0);
    return all;
  };
  try {
    const after = (await app.run(args, files, { stdout: only, stderr: both, decodeASCII: false })) as Tree;
    return { files: after, output, stdout, bytes: bytes(), ok: true };
  } catch (e) {
    if (e instanceof Exit) return { files: e.files, output, stdout, bytes: bytes(), ok: false };
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
  let current = files, bytes = new Uint8Array();
  // each job: the program's path (empty here), then the tool in the multi-call program ("clang", "-cc1", …)
  for (const [, ...rest] of jobs) {
    const step = await run(app, rest, current, true);
    if (!step.ok) return step;
    current = step.files;
    bytes = step.bytes;
  }
  return { files: current, stdout: "", bytes, output: plan.output.split("\n").filter((l) => !l.startsWith(' "') && !/^(clang|Target|Thread|InstalledDir|Build config)/.test(l)).join("\n"), ok: true };
}

/** Bytes of program in an Intel HEX file. */
const hexSize = (hex: string) =>
  hex.split(/\r?\n/).filter((l) => l.startsWith(":") && l.slice(7, 9) === "00").reduce((n, l) => n + parseInt(l.slice(1, 3), 16), 0);

export async function compile(app: Application, sketch: string): Promise<Compiled> {
  // the object to stdout: once a header was looked for where it is not (#include "Print.h" from a library,
  // tried next to it first), clang writes a file through a temporary one, which the runtime cannot
  const compiled = await clang(app, [...FLAGS, "-c", "sketch.cpp", "-o", "-"], { "sketch.cpp": prepareSketch(sketch) });
  if (!compiled.ok) return { failed: compiled.output.trim() };
  const linked = await run(app, ["ld.lld", "-o", "sketch.elf", ...LINK], { ...compiled.files, "sketch.o": compiled.bytes });
  if (!linked.ok) return { failed: linked.output.replaceAll("/arduino/lib/", "").trim() };
  // to stdout: writing a file, objcopy renames a temporary one, which the runtime cannot do
  const hexed = await run(app, ["llvm-objcopy", "-O", "ihex", "-R", ".eeprom", "sketch.elf", "-"], linked.files);
  if (!hexed.ok) return { failed: hexed.output.trim() };
  const hex = hexed.stdout;
  const size = hexSize(hex);
  if (size > FLASH) return { tooBig: size, flash: FLASH };
  return { hex, size };
}

