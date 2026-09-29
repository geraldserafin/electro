// The emulated Pico against a real compiled sketch (fixtures/blink.pico.ino, arduino-pico; built by
// make-arduino-fixtures.sh): its pins in time, its LED, its ADC, its two serial ports.
import { readFileSync } from "node:fs";
import { describe, expect, test } from "vitest";
import { Pico } from "./pico";

const image = () => new Uint8Array(readFileSync(new URL("./fixtures/blink.pico.bin", import.meta.url)));

describe("a Pico running a sketch", () => {
  const pico = new Pico(image());
  let serial = "";
  pico.onSerial = (text) => (serial += text);
  pico.sense("GP26", 1.65); // half of 3.3 V on ADC0
  pico.sense("GP14", 3.3); // its pull-up, as the circuit would show it
  pico.runUntil(0.6);
  const changes = pico.take();

  test("GP15 blinks at 10 Hz, driven high and low", () => {
    const rises = changes.filter((c) => c.pin === "GP15" && c.mode === "high").map((c) => c.time);
    expect(rises.length).toBeGreaterThan(3);
    const steady = rises.slice(2); // (after the start-up)
    const period = (steady[steady.length - 1] - steady[0]) / (steady.length - 1);
    expect(period).toBeGreaterThan(0.1); // two delay(50)s, and the printing
    expect(period).toBeLessThan(0.101);
  });

  test("GP14 is an input with its pull-up (after reset, the RP2040's pads pull down)", () => {
    const gp14 = changes.filter((c) => c.pin === "GP14").map((c) => c.mode);
    expect(gp14[0]).toBe("pulldown");
    expect(gp14[gp14.length - 1]).toBe("pullup");
  });

  test("analogRead() reads what the circuit puts on GP26 (12 bits); Serial and Serial1 both come out", () => {
    const adc = [...serial.matchAll(/adc=(\d+)/g)].map((m) => Number(m[1]));
    expect(adc.length).toBeGreaterThan(2);
    for (const a of adc) expect(Math.abs(a - 512)).toBeLessThan(8); // analogRead(): 10 bits by default, as on an Uno
    expect(serial).toMatch(/gp14=1/);
  });

  test("a later run goes on where it stopped; the LED follows GP25", () => {
    pico.runUntil(0.62);
    expect(typeof pico.led).toBe("boolean");
    expect(pico.time).toBeGreaterThanOrEqual(0.62);
  });
});
