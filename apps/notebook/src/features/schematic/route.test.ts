import { describe, expect, it } from "vitest";
import type { Point, SchematicData } from "@/shared/model/types";
import { library } from "./library";
import { updateElement } from "./model";
import { relaid, route } from "./route";

const r = (id: string, at: Point, rotation = 0) => ({ id, kind: "resistor", at, rotation, value: "1", text: null });
const way = (a: Point, b: Point): Point[] => [a, [b[0], a[1]], b];

/** Every square a wire passes, in order. */
const squares = (path: Point[]): Point[] => {
  const out: Point[] = [path[0]!];
  for (let i = 1; i < path.length; i++) {
    const [a, b] = [path[i - 1]!, path[i]!];
    const d: Point = [Math.sign(b[0] - a[0]), Math.sign(b[1] - a[1])];
    for (let p = a; p[0] !== b[0] || p[1] !== b[1]; ) {
      p = [p[0] + d[0], p[1] + d[1]];
      out.push(p);
    }
  }
  return out;
};
const inside = (path: Point[]) => squares(path).slice(1, -1);

describe("route", () => {
  it("goes around a resistor's body, not through it", () => {
    // R_1 from (0,0) to (4,0); a wire from (-2,0) to (6,0)
    const sch: SchematicData = { elements: [r("R_1", [0, 0])], wires: [] };
    const path = route(sch, library, [-2, 0], [6, 0], way([-2, 0], [6, 0]));
    expect(path[0]).toEqual([-2, 0]);
    expect(path.at(-1)).toEqual([6, 0]);
    expect(inside(path).some(([x, y]) => y === 0 && x >= 0 && x <= 4)).toBe(false);
  });

  it("joins two pins with one corner when nothing is in the way", () => {
    // R_1 (0,0)–(4,0) and R_2 standing at (8,2)–(8,6): R_1's right pin to R_2's top
    const sch: SchematicData = { elements: [r("R_1", [0, 0]), r("R_2", [8, 2], 90)], wires: [] };
    expect(route(sch, library, [4, 0], [8, 2], way([4, 0], [8, 2]))).toEqual([
      [4, 0],
      [8, 0],
      [8, 2],
    ]);
  });

  it("crosses another wire, never lies along it nor turns on it", () => {
    const sch: SchematicData = {
      elements: [],
      wires: [
        {
          points: [
            [0, 0],
            [10, 0],
          ],
        },
      ],
    };
    const path = route(sch, library, [2, -2], [8, 2], way([2, -2], [8, 2]));
    expect(inside(path).filter(([, y]) => y === 0).length).toBe(1); // it only crosses
    expect(path.slice(1, -1).some(([, y]) => y === 0)).toBe(false);
  });

  it("does not pass through another element's pin", () => {
    const sch: SchematicData = { elements: [r("R_1", [4, -2], 90)], wires: [] }; // pins (4,-2), (4,2)
    const path = route(sch, library, [0, 2], [8, 2], way([0, 2], [8, 2]));
    expect(inside(path).some(([x, y]) => x === 4 && y === 2)).toBe(false);
  });
});

describe("relaid", () => {
  it("a moved element's wire laid anew around what is in the way", () => {
    // R_1 (0,0)–(4,0), a wire from its right pin to R_2's top (8,2); R_1 moved under R_2's level
    const before: SchematicData = {
      elements: [r("R_1", [0, 0]), r("R_2", [8, 2], 90)],
      wires: [
        {
          points: [
            [4, 0],
            [8, 0],
            [8, 2],
          ],
        },
      ],
    };
    const after = relaid(before, updateElement(before, library, "R_1", { at: [0, 4] }), library, "R_1");
    const w = after.wires[0]!.points;
    expect(w[0]).toEqual([4, 4]);
    expect(w.at(-1)).toEqual([8, 2]);
    // not through R_2's body (8,2)–(8,6)
    expect(inside(w).some(([x, y]) => x === 8 && y > 2 && y <= 6)).toBe(false);
  });

  it("a wire with another joined along it: kept as dragged", () => {
    const before: SchematicData = {
      elements: [r("R_1", [0, 0])],
      wires: [
        {
          points: [
            [4, 0],
            [10, 0],
          ],
        },
        {
          points: [
            [7, 0],
            [7, 4],
          ],
        },
      ],
    };
    const dragged = updateElement(before, library, "R_1", { at: [0, 2] });
    expect(relaid(before, dragged, library, "R_1").wires[0]).toEqual(dragged.wires[0]);
  });
});
