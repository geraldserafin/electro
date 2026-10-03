import { describe, expect, it } from "vitest";
import type { ElementData, Point, SchematicData } from "@/shared/model/types";
import { library } from "./library";
import { attach, besides, movePoint, reversed, updateElement } from "./model";

const r = (id: string, at: Point, rotation = 0): ElementData => ({
  id,
  kind: "resistor",
  at,
  rotation,
  value: "1",
  text: null,
});
const u = (id: string, between: Point[]): ElementData => ({
  id,
  kind: "voltage_arrow",
  at: between[0]!,
  rotation: 0,
  value: null,
  text: "U",
  between,
});
const t = (id: string, at: Point): ElementData => ({ id, kind: "terminal", at, rotation: 0, value: null, text: null });

describe("marks", () => {
  it("a voltage across a resistor's pins drawn beside it; one between two wires, not", () => {
    const sch: SchematicData = {
      elements: [
        r("R1", [0, 0]),
        u("U1", [
          [0, 0],
          [4, 0],
        ]),
        u("U2", [
          [0, 4],
          [4, 8],
        ]),
      ],
      wires: [],
    };
    expect([...besides(sch, library)]).toEqual(["U1"]);
  });

  it("an arrow's end on a pin goes with the element moved", () => {
    const sch: SchematicData = {
      elements: [
        r("R1", [0, 0]),
        u("U1", [
          [0, 0],
          [4, 0],
        ]),
      ],
      wires: [],
    };
    const moved = updateElement(sch, library, "R1", { at: [0, 2] });
    expect(moved.elements[1]!.between).toEqual([
      [0, 2],
      [4, 2],
    ]);
  });

  it("a terminal moved along its wire: the wire whole where it was, split where it goes, the arrow's end with it", () => {
    const sch: SchematicData = {
      elements: [
        t("T1", [4, 0]),
        u("U1", [
          [4, 0],
          [0, 0],
        ]),
      ],
      wires: [
        {
          points: [
            [0, 0],
            [4, 0],
          ],
        },
        {
          points: [
            [4, 0],
            [10, 0],
          ],
        },
      ],
    };
    const next = movePoint(sch, library, [4, 0], [7, 0], [["U1", 0]], true);
    expect(next.elements.find((e) => e.id === "T1")!.at).toEqual([7, 0]);
    expect(next.elements.find((e) => e.id === "U1")!.between).toEqual([
      [7, 0],
      [0, 0],
    ]);
    expect(next.wires.map((w) => w.points)).toEqual([
      [
        [0, 0],
        [7, 0],
      ],
      [
        [7, 0],
        [10, 0],
      ],
    ]);
  });

  it("reversed: a voltage between two points from the other, a current along its wire the other way", () => {
    expect(
      reversed(
        u("U1", [
          [0, 0],
          [4, 0],
        ]),
      ),
    ).toEqual({
      between: [
        [4, 0],
        [0, 0],
      ],
    });
    expect(reversed({ id: "I1", kind: "current_arrow", at: [2, 0], rotation: 0, value: null, text: "I" })).toEqual({
      at: [3, 0],
      rotation: 180,
    });
  });

  it("a terminal put on a wire's corner splits the wire there (wires join by their ends)", () => {
    const sch: SchematicData = {
      elements: [t("T1", [4, 0])],
      wires: [
        {
          points: [
            [0, 0],
            [4, 0],
            [4, 4],
          ],
        },
      ],
    };
    expect(attach(sch, library, "T1").wires.map((w) => w.points)).toEqual([
      [
        [0, 0],
        [4, 0],
      ],
      [
        [4, 0],
        [4, 4],
      ],
    ]);
  });
});
