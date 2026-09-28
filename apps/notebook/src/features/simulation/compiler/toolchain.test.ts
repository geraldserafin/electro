// The in-page compiler, for real: clang and lld as WebAssembly (public/arduino/, from
// scripts/make-arduino-compiler.sh and make-arduino-sysroot.sh) compile a sketch, and the
// emulated Uno runs it. Skipped when the compiler has not been built.
import { existsSync, readFileSync } from "node:fs";
import { PinState } from "avr8js";
import { beforeAll, describe, expect, it } from "vitest";
import type { Application } from "@yowasp/runtime";
import { CLOCK, Uno } from "../arduino";
import { compile, toolchain } from "./toolchain";

const dir = new URL("../../../../public/arduino/", import.meta.url);
const built = existsSync(new URL("llvm.json", dir)) && existsSync(new URL("sysroot.tar", dir));
const read = (name: string) => readFileSync(new URL(name, dir));
const buffer = (b: Buffer) => b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength) as ArrayBuffer;

describe.skipIf(!built)("clang for AVR, as WebAssembly", () => {
  let app: Application;

  beforeAll(async () => {
    const { modules: names } = JSON.parse(read("llvm.json").toString()) as { modules: string[] };
    const { instantiate } = await import(/* @vite-ignore */ new URL("llvm.js", dir).href);
    const modules = Object.fromEntries(await Promise.all(names.map(async (n) => [n, await WebAssembly.compile(read(n))] as const)));
    app = await toolchain({ instantiate, modules, clangHeaders: buffer(read("clang-headers.tar")), sysroot: buffer(read("sysroot.tar")) });
  }, 120_000);

  it("compiles a sketch that runs: PWM, tone(), micros(), Serial", async () => {
    const sketch = readFileSync(new URL("../fixtures/features.ino", import.meta.url), "utf8");
    const result = await compile(app, sketch);
    if (!("hex" in result)) throw new Error(JSON.stringify(result));
    const uno = new Uno(result.hex);
    let serial = "";
    uno.onSerial = (c) => (serial += c);
    uno.sense("D2", 5);
    uno.runUntil(0.1);
    const d9 = uno.events.filter((e) => e.pin === "D9" && e.cycle / CLOCK > 0.02);
    const rises = d9.filter((e) => e.state === PinState.High).map((e) => e.cycle / CLOCK);
    expect(1 / ((rises[rises.length - 1] - rises[0]) / (rises.length - 1))).toBeCloseTo(490, -1);
    expect(uno.events.filter((e) => e.pin === "D8").length).toBeGreaterThan(100); // tone(8, 1000)
    expect(Number(serial.match(/us=(\d+)/)?.[1])).toBeGreaterThan(9900);
  }, 120_000);

  it("a function used above its definition, and a library (Servo)", async () => {
    const result = await compile(app, `#include <Servo.h>
Servo s;
void setup() { s.attach(9); later(); }
void loop() {}
void later() { s.write(90); }
`);
    if (!("hex" in result)) throw new Error(JSON.stringify(result));
    const uno = new Uno(result.hex);
    uno.runUntil(0.1);
    const d9 = uno.events.filter((e) => e.pin === "D9").map((e) => [e.cycle / CLOCK, e.state] as const);
    const i = d9.findIndex(([, s], k) => k > 2 && s === PinState.High);
    expect((d9[i + 1][0] - d9[i][0]) * 1000).toBeCloseTo(1.47, 1); // 90°: a 1.47 ms pulse
  }, 120_000);

  it("says what is wrong, on the sketch's own line", async () => {
    const result = await compile(app, "void setup() {\n  nope();\n}\nvoid loop() {}\n");
    expect(result).toHaveProperty("failed");
    expect((result as { failed: string }).failed).toMatch(/sketch\.ino:2:3: error: use of undeclared identifier 'nope'/);
  }, 120_000);
});
