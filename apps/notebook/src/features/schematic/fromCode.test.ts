// The code view back into a drawing: a circuit the kernel read from code laid out, and a drawing kept as
// it was when only values changed. The `FromCode`s are what the kernel's ``from_code`` returns for them.
import { expect, it } from "vitest";
import type { SchematicData } from "@/shared/model/types";
import golden from "./fixtures/netlists.json";
import { drawingFromCode, type FromCode, textOf } from "./fromCode";
import { layout } from "./layout";
import { library } from "./library";
import { elementsOf } from "./problem";

const rc: FromCode = {
  netlist: {
    elements: [
      { id: "E_1", kind: "voltage_source", nodes: ["n2", "n1"], value: "12" },
      { id: "R_1", kind: "resistor", nodes: ["n1", "A"], value: "1000" },
      { id: "R_2", kind: "resistor", nodes: ["A", "n2"], value: "2000" },
      { id: "C_1", kind: "capacitor", nodes: ["A", "n2"], value: "1µ" },
    ],
  },
  shape: {
    loop: [
      { element: "E_1", flip: false },
      { element: "R_1", flip: false },
      { node: "A" },
      {
        parallel: [
          { element: "R_2", flip: false },
          { element: "C_1", flip: false },
        ],
      },
    ],
  },
};

const cases = golden as unknown as Record<string, { schematic: SchematicData }>;

/** Each element's kind and points, the points renamed in order of appearance: one circuit, one answer. */
function circuit(elements: { id: string; kind: string; nodes: string[] }[]): string[] {
  const names = new Map<string, number>();
  const point = (n: string) => names.get(n) ?? names.set(n, names.size).get(n);
  return [...elements]
    .sort((a, b) => a.id.localeCompare(b.id))
    .map((e) => `${e.id} ${e.kind} ${e.nodes.map(point).join(" ")}`);
}

it("lays out a circuit read from code: the same elements on the same points", () => {
  const drawn = layout(rc.shape!, rc.netlist.elements, textOf);
  const read = elementsOf(drawn, library).elements;
  expect(circuit(read)).toEqual(circuit(rc.netlist.elements));
  expect(read.find((e) => e.id === "C_1")?.value).toBe("1µ");
});

it("keeps the drawing when only values change", () => {
  const old = cases.bridge.schematic;
  const elements = elementsOf(old, library).elements.map((e) => (e.id === "R_1" ? { ...e, value: "150" } : e));
  const back = drawingFromCode({ netlist: { elements }, shape: null }, old, library);
  if (!("schematic" in back)) throw new Error(JSON.stringify(back));
  expect(back.schematic.elements.map((e) => e.at)).toEqual(old.elements.map((e) => e.at));
  expect(back.schematic.elements.find((e) => e.id === "R_1")?.value).toBe("150");
});

it("a new element with no layout: only values can change in code", () => {
  const old = cases.bridge.schematic;
  const grown = [...elementsOf(old, library).elements, { id: "R9", kind: "resistor", nodes: ["GND", "GND"] }];
  const back = drawingFromCode({ netlist: { elements: grown }, shape: null }, old, library);
  expect("error" in back && back.error.issue?.type).toBe("OnlyValuesInCode");
});

it("a changed circuit is laid out anew", () => {
  const back = drawingFromCode(rc, cases.bridge.schematic, library);
  if (!("schematic" in back)) throw new Error(JSON.stringify(back));
  expect(circuit(elementsOf(back.schematic, library).elements)).toEqual(circuit(rc.netlist.elements));
});
