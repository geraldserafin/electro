// The test drawings read as circuits (fixtures/netlists.json: what Python made of them before the drawing
// moved to the page, kept as the answer).
import { describe, expect, it } from "vitest";
import type { SchematicData } from "@/shared/model/types";
import golden from "./fixtures/netlists.json";
import { library } from "./library";
import { connected, netlist, type Quantity, quantities } from "./netlist";

type Case = { schematic: SchematicData; netlist: unknown[]; quantities: Record<string, Record<string, number>> };
const cases = golden as unknown as Record<string, Case>;

/** A quantity as a sum of the solver's symbols (``I_R1``, ``V_A``), ground's potential left out. */
function linear(q: Quantity, k = 1, out: Record<string, number> = {}): Record<string, number> {
  const add = (name: string, c: number) => {
    out[name] = (out[name] ?? 0) + c;
  };
  if (q[0] === "sum") for (const [c, part] of q[1]) linear(part, k * c, out);
  else if (q[0] === "V") q[1] !== "GND" && add(`V_${q[1]}`, k);
  else if (q[0] === "U_between") {
    if (q[1] !== "GND") add(`V_${q[1]}`, k);
    if (q[2] !== "GND") add(`V_${q[2]}`, -k);
  } else add(`${q[0]}_${q[1]}`, k);
  return Object.fromEntries(Object.entries(out).filter(([, c]) => c));
}

describe("a drawing as the circuit it shows", () => {
  for (const [name, c] of Object.entries(cases)) {
    it(`${name}: its netlist`, () => {
      const got = netlist(c.schematic, library).elements.map(({ id, kind, value, text, nodes }) => ({
        id,
        kind,
        value: value ?? null,
        text: text ?? null,
        nodes,
      }));
      expect(got).toEqual(c.netlist);
    });
    it(`${name}: what its marks are`, () => {
      const { names } = netlist(c.schematic, library);
      const got = Object.fromEntries(quantities(c.schematic, library, names).map(([e, q]) => [e.id, linear(q)]));
      expect(got).toEqual(c.quantities);
    });
  }

  it("a wire passing over a pin does not connect, its end does", () => {
    const sch: SchematicData = {
      elements: [{ id: "R_1", kind: "resistor", at: [2, 0], rotation: 90, value: "1", text: null }],
      wires: [
        {
          points: [
            [0, 2],
            [4, 2],
          ],
        },
      ],
    };
    const nodes = connected(sch, library);
    expect(nodes.get("2,0")).not.toBe(nodes.get("0,2"));
    expect(nodes.get("0,2")).not.toBe(nodes.get("2,4"));
    const touching = connected(
      {
        ...sch,
        wires: [
          {
            points: [
              [0, 0],
              [2, 0],
            ],
          },
        ],
      },
      library,
    );
    expect(touching.get("0,0")).toBe(touching.get("2,0"));
  });

  it("a T-junction connects, a crossing does not", () => {
    const sch: SchematicData = {
      elements: [
        { id: "R_1", kind: "resistor", at: [0, 0], rotation: 0, value: "1", text: null },
        { id: "R_2", kind: "resistor", at: [2, -2], rotation: 90, value: "1", text: null },
      ],
      wires: [
        {
          points: [
            [4, 0],
            [6, 0],
          ],
        },
        {
          points: [
            [2, 2],
            [2, 4],
          ],
        },
      ],
    };
    expect(connected(sch, library).get("2,2")).not.toBe(connected(sch, library).get("0,0"));
    const crossing = {
      ...sch,
      wires: [
        ...sch.wires,
        {
          points: [
            [5, -3],
            [5, 3],
          ] as [number, number][],
        },
      ],
    };
    expect(connected(crossing, library).get("5,3")).not.toBe(connected(crossing, library).get("4,0"));
    const tee = {
      ...crossing,
      wires: [
        ...crossing.wires,
        {
          points: [
            [2, 2],
            [5, 2],
          ] as [number, number][],
        },
      ],
    };
    expect(connected(tee, library).get("2,4")).toBe(connected(tee, library).get("5,3"));
  });

  it("net labels of one name are one point", () => {
    const sch: SchematicData = {
      elements: [
        { id: "E_1", kind: "voltage_source", at: [0, 0], rotation: 0, value: "5", text: null },
        { id: "R_1", kind: "resistor", at: [10, 0], rotation: 0, value: "5", text: null },
        { id: "a", kind: "label", at: [4, 0], rotation: 0, value: null, text: "X" },
        { id: "b", kind: "label", at: [10, 0], rotation: 0, value: null, text: "X" },
        { id: "g1", kind: "ground", at: [0, 0], rotation: 0, value: null, text: null },
        { id: "g2", kind: "ground", at: [14, 0], rotation: 0, value: null, text: null },
      ],
      wires: [],
    };
    expect(netlist(sch, library).elements.map((e) => e.nodes)).toEqual([
      ["GND", "X"],
      ["X", "GND"],
    ]);
  });
});
