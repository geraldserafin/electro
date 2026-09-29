import { readFileSync } from "node:fs";
import { PinState } from "avr8js";
import { describe, expect, test } from "vitest";
import { CLOCK, Uno } from "./arduino";
import { buzzing, heard, listen, servoing, turn, watch } from "./peripherals";

/** A pin's square wave as the circuit gives it: a step lands on every edge, then steps of ``dt``. */
function pinWave(period: number, high: number, until: number, dt = 20e-6): [number, number][] {
  const samples: [number, number][] = [];
  for (let start = 0; start < until; start += period)
    for (const [from, to, v] of [[start, start + high, 5], [start + high, start + period, 0]] as const)
      for (let t = from; t < to - 1e-12; t = Math.min(to, t + dt)) samples.push([Math.min(to, t + dt), v]);
  return samples;
}

describe("servo", () => {
  test("its angle is the pulse's length, 544 µs to 2400 µs over 0° to 180°", () => {
    for (const [width, angle] of [[1.5e-3, 92.7], [544e-6, 0], [2.4e-3, 180]]) {
      const m = servoing("M_1", 0);
      for (const [t, v] of pinWave(20e-3, width, 0.1)) watch(m, v, t);
      expect(m.target).toBeCloseTo(angle, 0);
    }
  });

  test("its arm turns at 60° in 0.1 s", () => {
    const m = servoing("M_1", 0);
    m.target = 180;
    expect(turn(m, 0.05)).toBeCloseTo(120);
    expect(turn(m, 0.2)).toBe(180);
  });

  test("not a servo's pulse (too long, too short): it stays", () => {
    const m = servoing("M_1", 0);
    for (const [t, v] of pinWave(20e-3, 10e-3, 0.1)) watch(m, v, t);
    expect(m.target).toBe(90);
  });
});

describe("buzzer", () => {
  test("a passive one sounds at the frequency it is driven with", () => {
    const b = buzzing("BZ_1", 0, false);
    let last = 0;
    const samples = pinWave(1 / 440, 1 / 880, 0.5);
    for (const [t, v] of samples.filter(([t]) => t <= 0.25)) { listen(b, v, t - last); last = t; }
    heard(b, 0.25); // the first drawing: now it knows how far the wave swings
    for (const [t, v] of samples.filter(([t]) => t > 0.25)) { listen(b, v, t - last); last = t; }
    const { frequency, volume } = heard(b, 0.25);
    expect(frequency).toBeGreaterThan(430);
    expect(frequency).toBeLessThan(450);
    expect(volume).toBe(1);
  });

  test("an active one beeps at its own tone while powered, else not", () => {
    const b = buzzing("BZ_1", 0, true);
    listen(b, 5, 0.03);
    expect(heard(b, 0.033).frequency).toBe(2300);
    listen(b, 1, 0.03);
    expect(heard(b, 0.033).frequency).toBeNull();
  });
});

describe("driven by a real sketch (fixtures/peripherals.ino: Servo.write(45) on D9, tone(8, 440))", () => {
  // the pins' changes as the circuit sees them: a step lands on each (session.ts), then one step on
  const uno = new Uno(readFileSync(new URL("./fixtures/peripherals.hex", import.meta.url), "utf8"));
  uno.runUntil(0.3);
  const samples = (pin: string): [number, number][] => uno.events.filter((e) => e.pin === pin).flatMap((e, i, all) => {
    const t = e.cycle / CLOCK, before = i > 0 && all[i - 1].state === PinState.High ? 5 : 0;
    return [[t, before], [t + 1e-6, e.state === PinState.High ? 5 : 0]] as [number, number][];
  });

  test("the servo turns to 45°", () => {
    const m = servoing("M_1", 0);
    for (const [t, v] of samples("D9")) watch(m, v, t);
    expect(m.target).toBeCloseTo(45, 0);
  });

  test("the passive buzzer plays 440 Hz", () => {
    const b = buzzing("BZ_1", 0, false);
    let last = 0;
    const wave = samples("D8");
    for (const [t, v] of wave.filter(([t]) => t <= 0.1)) { listen(b, v, t - last); last = t; }
    heard(b, 0.1);
    for (const [t, v] of wave.filter(([t]) => t > 0.1 && t <= 0.3)) { listen(b, v, t - last); last = t; }
    expect(heard(b, 0.2).frequency).toBeCloseTo(440, -1);
  });
});
