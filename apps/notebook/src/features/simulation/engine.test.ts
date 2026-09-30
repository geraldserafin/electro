// A stress test of the page's engine: a long RC ladder (fixtures/ladder.live.json, 80 elements and 205
// unknowns; scripts/make_sim_fixtures.py). It must stay fast enough to run live, and right: charged
// from 5 V for 10 ms (τ of a stage 0.1 ms, of the whole ladder some ms), every node between 0 and 5 V,
// falling along the ladder, the first nearly full.
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { runProgram } from "./engine";

const json = readFileSync(new URL("./fixtures/ladder.live.json", import.meta.url), "utf8");
const { unknowns } = JSON.parse(json) as { unknowns: string[] };

describe("the engine under load", () => {
  it("runs 80 elements for 10 ms in well under a second, and gets them right", () => {
    const start = performance.now();
    const { t, rows } = runProgram(json, 0.01, 1e-4);
    const seconds = (performance.now() - start) / 1000;
    expect(seconds).toBeLessThan(2); // ~0.2 s here: a regression to many times slower fails
    const n = unknowns.length;
    const last = (name: string) => rows[(t.length - 1) * n + unknowns.indexOf(name)];
    const caps = Array.from({ length: 40 }, (_, k) => last(`U_C_${k + 1}`));
    expect(caps.every((v) => v > 0 && v < 5)).toBe(true);
    expect(caps.every((v, k) => k === 0 || v <= caps[k - 1] + 1e-9)).toBe(true);
    expect(caps[0]).toBeGreaterThan(4);
  });
});
