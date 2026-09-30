import { describe, expect, it } from "vitest";
import type { SchematicData } from "@/shared/model/types";
import { flowGraph, segmentCurrents } from "./flow";
import { library } from "./library";

// R_1's right pin (4, 0) → along the top to (8, 0) → down into R_2 (8, 4); a T at (6, 0) down to a ground
const value: SchematicData = {
  elements: [
    { id: "R_1", kind: "resistor", at: [0, 0], rotation: 0, value: "1", text: null },
    { id: "R_2", kind: "resistor", at: [8, 4], rotation: 90, value: "1", text: null },
    { id: "GND", kind: "ground", at: [6, 3], rotation: 0, value: null, text: null },
  ],
  wires: [
    {
      points: [
        [4, 0],
        [8, 0],
        [8, 4],
      ],
    },
    {
      points: [
        [6, 0],
        [6, 3],
      ],
    },
  ],
};
const nodes = { wires: ["n1", "n1"], pins: { R_1: [null, "n1"], R_2: ["n1", "n2"] } };

describe("the current along the wires", () => {
  const g = flowGraph(value, library, nodes, () => true);
  const along = (currents: Record<string, number[]>) =>
    Object.fromEntries(
      g.segments.map((s, i) => [`${s.a.join(",")}→${s.b.join(",")}`, +segmentCurrents(g, currents)[i].toFixed(6)]),
    );

  it("splits a wire where another one meets it", () => {
    expect(g.segments.map((s) => [s.a, s.b])).toEqual([
      [
        [80, 0],
        [120, 0],
      ],
      [
        [120, 0],
        [160, 0],
      ],
      [
        [160, 0],
        [160, 80],
      ],
      [
        [120, 0],
        [120, 60],
      ],
    ]);
  });

  it("follows the pins' currents, the ground taking what is left", () => {
    // 1 A out of R_1 (into its left pin, out of its right), all into R_2: none to the ground
    expect(along({ R_1: [1, -1], R_2: [1, -1] })).toEqual({
      "80,0→120,0": 1,
      "120,0→160,0": 1,
      "160,0→160,80": 1,
      "120,0→120,60": 0,
    });
    // R_2 takes a quarter: the rest goes down to the ground
    expect(along({ R_1: [1, -1], R_2: [0.25, -0.25] })).toEqual({
      "80,0→120,0": 1,
      "120,0→160,0": 0.25,
      "160,0→160,80": 0.25,
      "120,0→120,60": 0.75,
    });
  });
});
