import { readFileSync } from "node:fs";
import { PinState } from "avr8js";
import { describe, expect, test } from "vitest";
import { Uno } from "./arduino";
import { glyph, type Lcd, lcd, screen, watch } from "./lcd";

// x as the circuit would have it: the supply, the contrast, then RS, RW, E, D0–D7 (each against VSS)
const PINS = { power: 0, contrast: 1, backlight: undefined, rs: 2, rw: 3, e: 4, data: [5, 6, 7, 8, 9, 10, 11, 12] };
const text = (d: Lcd, x: ArrayLike<number>) => screen(d, x).lines.map((line) => line.map(glyph).join(""));

/** An Uno running ``hex`` wired to an LCD as Arduino's examples wire it: each pin change a sample. */
function wired(hex: string, wiring: Record<string, number>, until = 0.3) {
  const uno = new Uno(hex);
  uno.runUntil(until);
  const d = lcd("LCD_1", PINS);
  const x = new Float64Array(13);
  x[0] = 5;
  watch(d, x); // switched on
  for (const e of uno.events) {
    const i = wiring[e.pin];
    if (i === undefined) continue;
    x[i] = e.state === PinState.High ? 5 : 0;
    watch(d, x);
  }
  return { d, x };
}

describe("an HD44780 driven by Arduino's LiquidCrystal (fixtures/lcd.ino)", () => {
  const { d, x } = wired(readFileSync(new URL("./fixtures/lcd.hex", import.meta.url), "utf8"), {
    D12: PINS.rs,
    D11: PINS.e,
    D5: 9,
    D4: 10,
    D3: 11,
    D2: 12,
  });

  test("4-bit mode, both lines, the text where it was put", () => {
    expect(d.eightBit).toBe(false);
    expect(text(d, x)).toEqual(["Hello, world!   ", "  21.5°C        "]); // (a glyph from CGRAM: drawn, not text)
  });

  test("the custom glyph is in CGRAM", () => {
    expect([...d.cgram.slice(0, 8)]).toEqual([0b00000, 0b01010, 0b11111, 0b11111, 0b01110, 0b00100, 0, 0]);
    expect(screen(d, x).lines[1][0]).toBe(0);
  });

  test("the contrast: V0 at VSS is dark, V0 at VDD unreadable", () => {
    expect(screen(d, x).contrast).toBe(1);
    expect(screen(d, Object.assign(new Float64Array(x), { 1: 5 })).contrast).toBe(0);
  });

  test("without power it forgets", () => {
    const off = new Float64Array(x);
    off[0] = 0;
    watch(d, off);
    off[0] = 5;
    watch(d, off);
    expect(text(d, off)[0]).toBe(" ".repeat(16));
    expect(d.on).toBe(false);
  });
});
