// The first example: a Wheatstone bridge, every kind of cell.

import { newId } from "@/shared/model/cells";
import { blank } from "@/shared/model/format";
import type { Notebook } from "@/shared/model/types";

/** A first notebook that shows every kind of cell. */
export function example(): Notebook {
  return {
    ...blank("Sprawozdanie: mostek Wheatstone'a"),
    cells: [
      {
        id: newId(),
        type: "markdown",
        source:
          "## Cel ćwiczenia\n\nWyznaczyć nieznany opór $R_2$ z warunku równowagi mostka: amperomierz pokazuje $I_A = 0$.",
      },
      {
        id: newId(),
        type: "schematic",
        name: "mostek",
        schematic: {
          elements: [
            { id: "E_1", kind: "voltage_source", at: [0, 14], rotation: 270, value: "10", text: null },
            { id: "R_1", kind: "resistor", at: [8, 0], rotation: 90, value: "100", text: null },
            { id: "R_2", kind: "resistor", at: [8, 6], rotation: 90, value: null, text: null },
            { id: "R_3", kind: "resistor", at: [18, 0], rotation: 90, value: "50", text: null },
            { id: "R_4", kind: "resistor", at: [18, 6], rotation: 90, value: "100", text: null },
            { id: "A_1", kind: "ammeter", at: [11, 5], rotation: 0, value: "0", text: null }, // reading: 0 A
            { id: "gnd1", kind: "ground", at: [0, 14], rotation: 0, value: null, text: null },
          ],
          wires: [
            {
              points: [
                [0, 10],
                [0, 0],
                [8, 0],
              ],
            },
            {
              points: [
                [8, 0],
                [18, 0],
              ],
            },
            {
              points: [
                [8, 4],
                [8, 6],
              ],
            },
            {
              points: [
                [18, 4],
                [18, 6],
              ],
            },
            {
              points: [
                [8, 5],
                [11, 5],
              ],
            },
            {
              points: [
                [15, 5],
                [18, 5],
              ],
            },
            {
              points: [
                [8, 10],
                [8, 14],
              ],
            },
            {
              points: [
                [18, 10],
                [18, 14],
              ],
            },
            {
              points: [
                [0, 14],
                [18, 14],
              ],
            },
          ],
        },
      },
      {
        id: newId(),
        type: "code",
        outputs: [],
        source: 'sol = mostek.solve(find="R_2")  # mostek: the schematic above\nsteps(sol)',
      },
      {
        id: newId(),
        type: "markdown",
        source: "## Wyniki\n\nSchemat z prądami i napięciami w równowadze:",
      },
      {
        id: newId(),
        type: "code",
        outputs: [],
        source: "schematic(mostek, sol)",
      },
      {
        id: newId(),
        type: "markdown",
        source: "Obwody można też pisać kodem — `+` szeregowo, `|` równolegle:",
      },
      {
        id: newId(),
        type: "code",
        outputs: [],
        source:
          "uklad = (VoltageSource(12) + Resistor(2)) | Resistor(4) | ((Resistor(6) | CurrentSource(1)) + VoltageSource(6).transpose())\nschematic(uklad, uklad.solve())",
      },
    ],
  };
}
