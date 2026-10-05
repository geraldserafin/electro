import { expect, it } from "vitest";
import { fromDrawing, type Netlist, netlistOf, readable } from "./fromDrawing";
import { library } from "./library";
import { pictureOf } from "./picture";
import { elementsOf } from "./problem";

/** Each component's kind and points, the points renamed in order of appearance (ground `GND`). */
function circuit(elements: { id: string; kind: string; nodes: string[] }[]): string[] {
  const names = new Map<string, string>([
    ["0", "GND"],
    ["GND", "GND"],
  ]);
  const point = (n: string) => names.get(n) ?? names.set(n, `p${names.size}`).get(n);
  return [...elements].sort((a, b) => a.id.localeCompare(b.id)).map((e) => `${e.id} ${e.kind} ${e.nodes.map(point)}`);
}

const drawn = (data: Netlist, strict = false) => {
  const got = fromDrawing(data, library, strict);
  if (!("schematic" in got)) throw new Error(JSON.stringify(got));
  return got;
};

// the worksheet's task 3: E on the left, R on top, R1 over R2 in the middle, R3 on the right; the bottom
// wire runs under R2's pin: touching, so joined
const task3: Netlist = {
  elements: [
    {
      id: "E1",
      kind: "voltage_source",
      value: "45",
      nodes: ["0", "A"],
      at: [
        [0, 12],
        [0, 0],
      ],
    },
    {
      id: "R",
      kind: "resistor",
      value: "10",
      nodes: ["A", "B"],
      at: [
        [0, 0],
        [8, 0],
      ],
    },
    {
      id: "R1",
      kind: "resistor",
      value: "6",
      nodes: ["B", "C"],
      at: [
        [8, 0],
        [8, 6],
      ],
    },
    {
      id: "R2",
      kind: "resistor",
      value: "4",
      nodes: ["C", "0"],
      at: [
        [8, 6],
        [8, 12],
      ],
    },
    {
      id: "R3",
      kind: "resistor",
      value: "10",
      nodes: ["B", "0"],
      at: [
        [14, 0],
        [14, 12],
      ],
    },
  ],
  wires: [
    [
      [8, 0],
      [14, 0],
    ],
    [
      [0, 12],
      [14, 12],
    ],
  ],
};

it("draws a circuit as its picture has it", () => {
  const { schematic, rerouted } = drawn(task3);
  const at = Object.fromEntries(schematic.elements.map((e) => [e.id, [e.at, e.rotation]]));
  expect(at.R).toEqual([[2, 0], 0]); // in the middle of its 8 units, as on the picture
  expect([at.R1[1], at.R3[1]]).toEqual([90, 90]); // standing, as drawn
  expect(rerouted).toBe(false);
  expect(circuit(elementsOf(schematic, library).elements)).toEqual(circuit(task3.elements));
});

it("lays the wires anew where they join other than the nodes say, or says so", () => {
  const broken = { ...task3, wires: [task3.wires![1]] }; // the right branch's top wire left out
  const anew = drawn(broken);
  expect(anew.rerouted).toBe(true);
  const at = (s: typeof anew) => Object.fromEntries(s.schematic.elements.map((e) => [e.id, e.at]));
  expect(at(anew)).toEqual(at(drawn(task3)));
  expect(circuit(elementsOf(anew.schematic, library).elements)).toEqual(circuit(task3.elements));
  const strict = fromDrawing(broken, library, true);
  expect("error" in strict && strict.error.mismatch).toEqual(["node B is drawn as 2 separate pieces"]);
  const clash = {
    ...task3,
    elements: [
      ...task3.elements.slice(0, 4),
      {
        ...task3.elements[4],
        at: [
          [8, 6],
          [8, 12],
        ],
      },
    ],
  };
  const joined = fromDrawing(clash as Netlist, library);
  expect("error" in joined && joined.error.mismatch?.length).toBeTruthy();
});

it("says what is wrong with the circuit itself", () => {
  const lone = { ...task3, elements: [...task3.elements.slice(0, 4), { ...task3.elements[4], nodes: ["B", "D"] }] };
  const got = fromDrawing(lone, library);
  expect("error" in got && got.error.dangling).toEqual(["R3's terminal 2 (node D) is joined to nothing"]);
  const named = (id: string, kind = "resistor") => ({
    elements: [{ ...task3.elements[1], id, kind }, ...task3.elements.slice(2)],
    wires: task3.wires,
  });
  const evil = fromDrawing(named("x)+__import__('os').system('x')"), library);
  expect("error" in evil && evil.error.issue?.type).toBe("BadName");
  const unknown = fromDrawing(named("Q1", "flux_capacitor"), library);
  expect("error" in unknown && unknown.error.issue?.type).toBe("UnknownKind");
  const tiny = fromDrawing(
    {
      elements: [
        {
          ...task3.elements[1],
          at: [
            [0, 0],
            [0, 0],
          ],
        },
      ],
      wires: [],
    },
    library,
  );
  expect("error" in tiny).toBe(true);
});

it("mends what a model may slip: drawn too small, askew, wires as text or flat", () => {
  const small = {
    elements: [
      ...task3.elements.slice(0, 4).map((e) => ({ ...e, at: e.at!.map(([x, y]) => [x / 2, y / 2]) })),
      {
        ...task3.elements[4],
        at: [
          [7, 0],
          [6, 6],
        ],
      },
    ],
    wires: ["[4, 0], [7, 0]", [0, 6, 7, 6]],
  } as unknown as Netlist;
  const at = Object.fromEntries(drawn(small).schematic.elements.map((e) => [e.id, e.at]));
  expect(at.R).toEqual([2, 0]); // as before: scaled ×2
});

it("an open network: its ends terminals, as drawn", () => {
  const divider: Netlist = {
    elements: [
      { id: "T1", kind: "terminal", nodes: ["A"], at: [[0, 0]] },
      {
        id: "R1",
        kind: "resistor",
        value: "100",
        nodes: ["A", "B"],
        at: [
          [4, 0],
          [4, 6],
        ],
      },
      {
        id: "R2",
        kind: "resistor",
        value: "100",
        nodes: ["B", "C"],
        at: [
          [4, 6],
          [4, 12],
        ],
      },
      { id: "T2", kind: "terminal", nodes: ["C"], at: [[0, 12]] },
    ],
    wires: [
      [
        [0, 0],
        [4, 0],
      ],
      [
        [0, 12],
        [4, 12],
      ],
    ],
  };
  const { schematic, rerouted } = drawn(divider, true);
  expect(rerouted).toBe(false);
  expect(schematic.elements.filter((e) => e.kind === "terminal")).toHaveLength(2);
});

it("draws arrows as marks, named, not of the circuit; and the picture shows them", async () => {
  const data: Netlist = {
    elements: [
      {
        id: "E",
        kind: "voltage_source",
        value: "12",
        nodes: ["0", "A"],
        at: [
          [0, 8],
          [0, 0],
        ],
      },
      {
        id: "R1",
        kind: "resistor",
        value: "6",
        nodes: ["A", "0"],
        at: [
          [8, 0],
          [8, 8],
        ],
      },
      {
        id: "i",
        kind: "current_arrow",
        text: "I_1",
        nodes: [],
        at: [
          [8, 5],
          [8, 6],
        ],
      },
      {
        id: "u",
        kind: "voltage_arrow",
        text: "U",
        nodes: [],
        at: [
          [11, 8],
          [11, 0],
        ],
      },
    ],
    wires: [
      [
        [0, 0],
        [8, 0],
      ],
      [
        [0, 8],
        [8, 8],
      ],
    ],
  };
  const { schematic } = drawn(data, true);
  const arrows = Object.fromEntries(schematic.elements.map((e) => [e.id, e]));
  expect([arrows.i.rotation, arrows.i.text]).toEqual([90, "I_1"]);
  expect([arrows.u.rotation, arrows.u.span]).toEqual([270, 8]); // up, 8 units long
  const svg = await pictureOf(schematic, library);
  expect(svg.startsWith("<svg")).toBe(true);
  expect(svg).toContain(">U</text>");
  expect(netlistOf(schematic, library).elements.map((e) => e.nodes)).toEqual([
    ["0", "n1"],
    ["n1", "0"],
  ]);
});

it("writes numbers as on a drawing", () => {
  expect([readable("2200"), readable("0.0001"), readable("1234"), readable("R")]).toEqual([
    "2.2k",
    "100µ",
    "1234",
    "R",
  ]);
});
