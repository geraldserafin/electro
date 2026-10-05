import { expect, it } from "vitest";
import { bodeSvg, histogramSvg, traceSvg } from "./svg";

it("draws a waveform, a frequency response and a spread", () => {
  const t = Array.from({ length: 50 }, (_, k) => k / 49);
  const trace = traceSvg({ x: { name: "t", unit: "s" }, t, series: { V_A: t.map((s) => 5 * (1 - Math.exp(-s))) } });
  expect(trace).toContain("<polyline");
  expect(trace).toContain('V<tspan class="sub" dy="3">A</tspan>');
  const f = [10, 100, 1000, 10000];
  const bode = bodeSvg({
    f,
    input: "E_1",
    outputs: { U_C_1: { gain: [0, -0.1, -3, -20], phase: [0, -6, -45, -84] } },
    cutoffs: [1000],
  });
  expect(bode).toContain("f<tspan");
  expect(bode).toContain("1kHz");
  const spread = histogramSvg({ values: { V_A: [5.9, 6, 6.1, 6, 5.95] } });
  expect(spread.match(/<rect/g)?.length).toBe(24);
});
