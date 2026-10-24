// A drawing's code, written by the page: series and parallel where it is made of them, else walks from point
// to point; a variable only for what is used more than once; its data and what is sought, solved at the end;
// names that cannot write code of their own.
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
    "petla.final({E_1: 12, R_1: 4})",
  ]);
  expect(codeOf({ elements, given: [] }, "Układ 1")).toContain("\nukład1 = ");
});

// (a voltmeter called V is V_: V is the potential's)
it("writes parallel, named points, parameters, parts, readings and marks", () => {
  const elements: NetlistElement[] = [
    { id: "E", kind: "sine_source", nodes: ["GND", "A"], value: "5", params: { f: "1k", phase: 0 } },
    { id: "R", kind: "resistor", nodes: ["A", "B"], value: "1k" },
    { id: "D", kind: "diode", nodes: ["B", "GND"], value: null, part: "1N4148" },
    { id: "V", kind: "voltmeter", nodes: ["B", "GND"], value: "0.7" },
  ];
  const code = codeOf({ elements, given: [[["I", "R"], "2m"]] }, "uklad");
  expect(code).toContain('uklad = ~(E >> Node("A") >> R >> Node("B") >> (D | V_))');
  expect(code).toContain(
    'uklad.final({E: {"": 5, "f": "1k", "phase": 0}, R: "1k", D: part("1N4148"), U(V_): 0.7, I(R): "2m"})',
  );
});

it("writes a bridge as walks, its points named once, and what is sought", () => {
  const elements: NetlistElement[] = [
    { id: "E_1", kind: "voltage_source", nodes: ["n1", "n2"], value: "220" },
    { id: "R_1", kind: "resistor", nodes: ["n2", "n3"], value: "5" },
    { id: "R_2", kind: "resistor", nodes: ["n2", "n4"], value: "20" },
    { id: "R_3", kind: "resistor", nodes: ["n4", "n1"], value: "5" },
    { id: "R_4", kind: "resistor", nodes: ["n3", "n1"], value: "10" },
    { id: "R_5", kind: "resistor", nodes: ["n3", "n4"], value: null },
  ];
  const code = codeOf(
    {
      elements,
      given: [],
      find: [
        ["I", "R_1"],
        ["Rth", "R_5"],
      ],
    },
    "układ2",
  ).split("\n");
  expect(code.slice(-6)).toEqual([
    'n1, n2, n3, n4 = Node("n1"), Node("n2"), Node("n3"), Node("n4")',
    "układ2 = (",
    "    (n1 >> E_1 >> n2 >> R_1 >> n3 >> R_4 >> n1 >> R_3 >> n4 >> R_2 >> n2)",
    "    @ (n3 >> R_5 >> n4)",
    ")",
    "układ2.final({E_1: 220, R_1: 5, R_2: 20, R_3: 5, R_4: 10}, find=[I(R_1), Thevenin(R_5)])",
  ]);
});

it("writes an element used once where it is used", () => {
  const elements = loop(["E", "voltage_source", "1"], ["R", "resistor", null]);
  expect(codeOf({ elements, given: [] }, "u").split("\n")).toEqual([
    'E = VoltageSource("E")',
    'u = ~(E >> Resistor("R"))',
    "u.final({E: 1})",
  ]);
});

it("no name writes code of its own", () => {
  const elements = loop(['E"); import os; ("', "voltage_source", "1"], ["class", "resistor", '1"); x("']);
  const code = codeOf({ elements, given: [] }, "u");
  expect(code).not.toMatch(/^[^"]*import os/m);
  expect(code).toContain('class_ = Resistor("class")'.replace("class_", "_class"));
  expect(code).toContain('"1\\"); x(\\""');
  expect(variable("1 test")).toBe("_1test");
});

it("shows what the code view says it shows, the circuit's final call where it stood", () => {
  const elements = loop(["E", "voltage_source", "1"], ["R", "resistor", "2"]);
  const code = codeOf({ elements, given: [], find: [["I", "R"]] }, "u", "sol = __final__\nsteps(sol)");
  expect(code.split("\n").slice(-2)).toEqual(["sol = u.final({E: 1, R: 2}, find=[I(R)])", "steps(sol)"]);
});
