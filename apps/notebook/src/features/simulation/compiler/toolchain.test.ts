// The in-page compiler, for real: clang and lld as WebAssembly (public/arduino/, from
// scripts/make-arduino-compiler.sh, make-arduino-sysroot.sh and make-pico-sysroot.sh) compile a sketch,
// and the emulated Uno or Pico runs it. Skipped when the compiler has not been built.
import { existsSync, readFileSync } from "node:fs";
import { PinState } from "avr8js";
import { beforeAll, describe, expect, it } from "vitest";
import { CLOCK, Uno } from "../arduino";
import { Backpack, Clock, Oled } from "../i2c";
import { lcd, screen, watch } from "../lcd";
import { Pico } from "../pico";
import { Runner } from "../runner";
import { WIDTH } from "../tft";
import { compile, toolchain, type Board, type Toolchain } from "./toolchain";

const dir = new URL("../../../../public/arduino/", import.meta.url);
const built = (sysroot: string) => existsSync(new URL("llvm.json", dir)) && existsSync(new URL(sysroot, dir));
const read = (name: string) => readFileSync(new URL(name, dir));
const buffer = (b: Buffer) => b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength) as ArrayBuffer;

async function load(board: Board, sysroot: string) {
  const { modules: names } = JSON.parse(read("llvm.json").toString()) as { modules: string[] };
  const { instantiate } = await import(/* @vite-ignore */ new URL("llvm.js", dir).href);
  const modules = Object.fromEntries(await Promise.all(names.map(async (n) => [n, await WebAssembly.compile(read(n))] as const)));
  return toolchain({ instantiate, modules, clangHeaders: buffer(read("clang-headers.tar")), sysroot: buffer(read(sysroot)) }, board);
}

describe.skipIf(!built("sysroot.tar"))("clang for AVR, as WebAssembly", () => {
  let app: Toolchain;
  beforeAll(async () => { app = await load("uno", "sysroot.tar"); }, 120_000);

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

  it("LiquidCrystal: the display says what the sketch printed", async () => {
    const result = await compile(app, readFileSync(new URL("../fixtures/lcd.ino", import.meta.url), "utf8"));
    if (!("hex" in result)) throw new Error(JSON.stringify(result));
    const uno = new Uno(result.hex);
    uno.runUntil(0.3);
    const wiring: Record<string, number> = { D12: 2, D11: 4, D5: 9, D4: 10, D3: 11, D2: 12 }; // as lcd.test.ts
    const d = lcd("LCD_1", { power: 0, contrast: 1, backlight: undefined, rs: 2, rw: 3, e: 4, data: [5, 6, 7, 8, 9, 10, 11, 12] });
    const x = new Float64Array(13);
    x[0] = 5;
    watch(d, x);
    for (const e of uno.events) {
      if (wiring[e.pin] === undefined) continue;
      x[wiring[e.pin]] = e.state === PinState.High ? 5 : 0;
      watch(d, x);
    }
    expect(screen(d, x).text[0].join("")).toBe("Hello, world!   ");
  }, 120_000);

  it("a header included in quotes, looked for next to the sketch first", async () => {
    const result = await compile(app, '#include "Print.h"\nvoid setup() {}\nvoid loop() {}\n');
    if (!("hex" in result)) throw new Error(JSON.stringify(result));
  }, 120_000);

  it("I²C: Wire, LiquidCrystal_I2C, Adafruit_SSD1306 (with GFX, BusIO), RTClib", async () => {
    const build = async (name: string) => {
      const result = await compile(app, readFileSync(new URL(`../fixtures/${name}.ino`, import.meta.url), "utf8"));
      if (!("hex" in result)) throw new Error(JSON.stringify(result));
      return new Uno(result.hex);
    };
    const lcdUno = await build("i2c_lcd"), backpack = new Backpack("LCD_1", 0x27, () => true);
    lcdUno.i2c.devices.push(backpack);
    lcdUno.runUntil(1.5);
    expect(backpack.screen().text[0].join("")).toBe("I2C works       ");
    const oledUno = await build("oled"), oled = new Oled("OLED_1", 0x3c, () => true);
    oledUno.i2c.devices.push(oled);
    oledUno.runUntil(0.5);
    expect(oled.pixels().rows[63][127]).toBe(1);
    const rtcUno = await build("rtc");
    rtcUno.i2c.devices.push(new Clock("RTC_1", 0x68, () => true, () => rtcUno.time));
    let serial = "";
    rtcUno.onSerial = (c) => (serial += c);
    rtcUno.runUntil(2.2);
    expect(serial).toMatch(/2024-5-17 13:45:3[12]/);
  }, 240_000);

  it("says what is wrong, on the sketch's own line", async () => {
    const result = await compile(app, "void setup() {\n  nope();\n}\nvoid loop() {}\n");
    expect(result).toHaveProperty("failed");
    expect((result as { failed: string }).failed).toMatch(/sketch\.ino:2:3: error: use of undeclared identifier 'nope'/);
  }, 120_000);
});

describe.skipIf(!built("pico.tar"))("clang for a Pico (ARM), as WebAssembly", () => {
  let app: Toolchain;
  beforeAll(async () => { app = await load("pico", "pico.tar"); }, 120_000);
  const build = async (sketch: string) => {
    const result = await compile(app, sketch);
    if (!("image" in result)) throw new Error(JSON.stringify(result));
    return result.image;
  };

  it("a sketch that runs: GP15 blinking, analogRead(), Serial and Serial1", async () => {
    const pico = new Pico(await build(readFileSync(new URL("../fixtures/blink.pico.ino", import.meta.url), "utf8")));
    let serial = "";
    pico.onSerial = (text) => (serial += text);
    pico.sense("GP26", 1.65);
    pico.sense("GP14", 3.3);
    pico.runUntil(0.6);
    const rises = pico.take().filter((c) => c.pin === "GP15" && c.mode === "high").map((c) => c.time).slice(2);
    expect((rises[rises.length - 1] - rises[0]) / (rises.length - 1)).toBeCloseTo(0.1, 2);
    expect(Math.abs(Number(serial.match(/adc=(\d+)/)?.[1]) - 512)).toBeLessThan(8);
    expect(serial).toMatch(/gp14=1/);
  }, 120_000);

  it("Adafruit_ILI9341 (with GFX, BusIO, SPI): the picture as from arduino-cli's build", async () => {
    const image = await build(readFileSync(new URL("../fixtures/tft.pico.ino", import.meta.url), "utf8"));
    const runner = new Runner(JSON.parse(readFileSync(new URL("../fixtures/tft.live.json", import.meta.url), "utf8")), []);
    runner.attach("PICO_1", { board: "pico", image });
    (runner.session.boards[0].chip as Pico).adaptive = false;
    runner.advanceTo(1.0, 1e-3);
    let picture: Uint8ClampedArray | undefined;
    for (let p = runner.pictures(true)?.TFT_1; p; p = runner.pictures(true)?.TFT_1) picture = p;
    const at = (x: number, y: number) => Array.from(picture!.slice((y * WIDTH + x) * 4, (y * WIDTH + x) * 4 + 3));
    expect(at(10, 10)).toEqual([0, 0, 255]);
    expect(at(300, 220)).toEqual([255, 0, 0]);
  }, 120_000);

  it("the other libraries link: Servo, EEPROM, LiquidCrystal_I2C, SSD1306, RTClib, the C++ library; the examples' game", async () => {
    await build(readFileSync(new URL("../fixtures/hell.pico.ino", import.meta.url), "utf8"));
    await build(`#include <Servo.h>
#include <EEPROM.h>
#include <LiquidCrystal_I2C.h>
#include <Adafruit_SSD1306.h>
#include <RTClib.h>
#include <vector>
Servo s; LiquidCrystal_I2C lcd(0x27, 16, 2); Adafruit_SSD1306 oled(128, 64, &Wire); RTC_DS1307 rtc; std::vector<int> v;
void setup() { s.attach(2); lcd.init(); oled.begin(SSD1306_SWITCHCAPVCC, 0x3C); rtc.begin(); EEPROM.begin(256); v.push_back(3); later(); }
void loop() {}
void later() { Serial.println(sqrt(2.0) + v[0]); }
`);
  }, 120_000);

  it("says what is wrong, on the sketch's own line", async () => {
    const result = await compile(app, "void setup() {\n  nope();\n}\nvoid loop() {}\n");
    expect((result as { failed: string }).failed).toMatch(/sketch\.ino:2:3: error: use of undeclared identifier 'nope'/);
  }, 120_000);
});
