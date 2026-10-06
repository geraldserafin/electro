// A drawing's code, written by the page: series and parallel where it is made of them, else each element
// at its points; its data; names that cannot write code of their own.
import { expect, it } from "vitest";
import { codeOf, variable } from "./code";
import type { NetlistElement } from "./problem";

/** Elements in one loop from ground: each `[id, kind, value]`. */
function loop(...elements: [string, string, string | null][]): NetlistElement[] {
  const nodes = ["GND", ...elements.slice(1).map((_, k) => `n${k + 1}`), "GND"];
  return elements.map(([id, kind, value], k) => ({ id, kind, value, nodes: [nodes[k], nodes[k + 1]] }));
}

it("writes a loop", () => {
  const elements = loop(["E_1", "voltage_source", "12"], ["R_1", "resistor", "4"]);
  expect(codeOf({ elements, given: [] }, "petla").split("\n")).toEqual([
    'E_1 = VoltageSource("E_1")',
    'R_1 = Resistor("R_1")',
    "petla = ~(E_1 >> R_1)",
    "petla_values = {E_1: 12, R_1: 4}",
  ]);
  expect(codeOf({ elements, given: [] }, "Układ 1")).toContain("\nukład1 = ");
});

it("writes parallel, named points, parameters, parts, readings and marks", () => {
  const elements: NetlistElement[] = [
    { id: "E", kind: "sine_source", nodes: ["GND", "A"], value: "5", params: { f: "1k", phase: 0 } },
    { id: "R", kind: "resistor", nodes: ["A", "B"], value: "1k" },
    { id: "D", kind: "diode", nodes: ["B", "GND"], value: null, part: "1N4148" },
    { id: "V", kind: "voltmeter", nodes: ["B", "GND"], value: "0.7" },
  ];
  const code = codeOf({ elements, given: [[["I", "R"], "2m"]] }, "uklad");
  expect(code).toContain('node_A = Node("A")\nnode_B = Node("B")');
  expect(code).toContain("~(E >> node_A >> R >> node_B >> (D | V))");
  expect(code).toContain('{E: {"": 5, "f": "1k", "phase": 0}, R: "1k", D: part("1N4148"), U(V): 0.7, I(R): "2m"}');
});

it("writes a bridge element by element", () => {
  const elements: NetlistElement[] = [
    { id: "E", kind: "voltage_source", nodes: ["GND", "A"], value: "10" },
    { id: "R1", kind: "resistor", nodes: ["A", "B"], value: "1" },
    { id: "R2", kind: "resistor", nodes: ["A", "C"], value: "1" },
    { id: "R3", kind: "resistor", nodes: ["B", "C"], value: "1" },
    { id: "R4", kind: "resistor", nodes: ["B", "GND"], value: "1" },
    { id: "R5", kind: "resistor", nodes: ["C", "GND"], value: "1" },
  ];
  expect(codeOf({ elements, given: [] }, "m")).toContain(
    "(\n    (GND >> E >> node_A)\n    @ (node_A >> R1 >> node_B)\n",
  );
});

it("no name writes code of its own", () => {
  const elements = loop(['E"); import os; ("', "voltage_source", "1"], ["class", "resistor", '1"); x("']);
  const code = codeOf({ elements, given: [] }, "u");
  expect(code).not.toMatch(/^[^"]*import os/m);
  expect(code).toContain('class_ = Resistor("class")'.replace("class_", "_class"));
  expect(code).toContain('"1\\"); x(\\""');
  expect(variable("1 test")).toBe("_1test");
});
