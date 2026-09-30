import { describe, expect, it } from "vitest";
import { spectrum } from "./spectrum";

describe("spectrum", () => {
  it("finds a sine's amplitude at its frequency, and the mean at 0 Hz", () => {
    const t = Array.from({ length: 2000 }, (_, k) => k / 10000); // 0.2 s at 10 kHz
    const v = t.map((s) => 1 + 5 * Math.sin(2 * Math.PI * 50 * s));
    const { f, a } = spectrum(t, v, 0, 0.2);
    const peak = a.indexOf(Math.max(...a.slice(1)));
    expect(f[peak]).toBeCloseTo(50, 5);
    expect(a[peak]).toBeCloseTo(5, 1);
    expect(a[0]).toBeCloseTo(1, 2);
  });

  it("gives a square wave's odd harmonics", () => {
    const t = Array.from({ length: 4000 }, (_, k) => k / 20000);
    const v = t.map((s) => ((s * 100) % 1 < 0.5 ? 1 : 0));
    const { f, a } = spectrum(t, v, 0, 0.2);
    const at = (hz: number) => a[Math.round(hz / f[1])];
    expect(at(100)).toBeCloseTo(2 / Math.PI, 1);
    expect(at(300)).toBeCloseTo(2 / (3 * Math.PI), 1);
    expect(at(200)).toBeLessThan(0.02);
  });
});
