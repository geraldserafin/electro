// The emulated Uno against a real compiled sketch (fixtures/features.ino; make-arduino-fixtures.sh
// compiles it): what the pins do in time, and what the sketch says on its serial port.
import { readFileSync } from "node:fs";
import { PinState } from "avr8js";
import { describe, expect, it } from "vitest";
import { CLOCK, Uno } from "./arduino";

const hex = readFileSync(new URL("./fixtures/features.hex", import.meta.url), "utf8");

function start() {
  const uno = new Uno(hex);
  let serial = "";
  uno.onSerial = (c) => (serial += c);
  uno.sense("D2", 5); // the pull-up holds it high
  return { uno, serial: () => serial };
}

/** A pin's changes between two times: [time, high?] each. */
function edges(uno: Uno, pin: string, from: number, to: number): [number, boolean][] {
  return uno.events.filter((e) => e.pin === pin && e.cycle / CLOCK >= from && e.cycle / CLOCK < to)
    .map((e) => [e.cycle / CLOCK, e.state === PinState.High]);
}

/** Frequency and duty cycle from a pin's edges. */
function wave(changes: [number, boolean][]) {
  const rises = changes.filter(([, high]) => high).map(([t]) => t);
  const period = (rises[rises.length - 1] - rises[0]) / (rises.length - 1);
  let high = 0;
  for (let i = 0; i + 1 < changes.length; i++) if (changes[i][1]) high += changes[i + 1][0] - changes[i][0];
  const span = changes[changes.length - 1][0] - changes[0][0];
  return { frequency: 1 / period, duty: high / span };
}

describe("an Uno running a sketch", () => {
  it("analogWrite: PWM at ≈ 490 Hz, 64/255 of the time high", () => {
    const { uno } = start();
    uno.runUntil(0.1);
    const pwm = wave(edges(uno, "D9", 0.02, 0.1));
    expect(pwm.frequency).toBeGreaterThan(480);
    expect(pwm.frequency).toBeLessThan(500);
    expect(pwm.duty).toBeCloseTo(64 / 255, 1);
  });

  it("tone: a square wave at the frequency asked", () => {
    const { uno } = start();
    uno.runUntil(0.1);
    const t = wave(edges(uno, "D8", 0.02, 0.1));
    expect(t.frequency).toBeCloseTo(1000, -1);
    expect(t.duty).toBeCloseTo(0.5, 1);
  });

  it("micros() and delay() agree: 10 ms is 10 000 µs", () => {
    const { uno, serial } = start();
    uno.runUntil(0.05);
    const us = Number(serial().match(/us=(\d+)/)?.[1]);
    expect(us).toBeGreaterThan(9900);
    expect(us).toBeLessThan(10100);
  });

  it("an interrupt on a falling edge of a pin the circuit drives", () => {
    const { uno, serial } = start();
    uno.runUntil(0.02);
    for (let k = 0; k < 5; k++) { // five presses of a button to ground
      uno.sense("D2", 0);
      uno.runUntil(0.03 + k * 0.02);
      uno.sense("D2", 5);
      uno.runUntil(0.04 + k * 0.02);
    }
    uno.sense("D2", 2.2); // between the thresholds: stays HIGH (hysteresis), no sixth edge
    uno.runUntil(0.25);
    expect(serial()).toMatch(/falls=5\r\n$/);
  });

  it("Serial.read(): what is typed comes back upper-cased", () => {
    const { uno, serial } = start();
    uno.runUntil(0.02);
    uno.send("abc");
    uno.runUntil(0.05);
    expect(serial()).toContain("ABC");
  });
});
