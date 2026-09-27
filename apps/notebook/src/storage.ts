import type { Cell, CellType, Notebook } from "./types";

const KEY = "electro-notebook";

export const newId = () => Math.random().toString(36).slice(2, 10);

export function newCell(type: CellType): Cell {
  if (type === "markdown") return { id: newId(), type, source: "" };
  if (type === "code") return { id: newId(), type, source: "", outputs: [] };
  return { id: newId(), type, name: "uklad", schematic: { elements: [], wires: [] } };
}

export function load(): Notebook {
  try {
    const saved = localStorage.getItem(KEY);
    if (saved) return JSON.parse(saved);
  } catch {
    // private mode or broken data: start fresh
  }
  return example();
}

export function save(notebook: Notebook) {
  try {
    localStorage.setItem(KEY, JSON.stringify(notebook));
  } catch {
    // storage full or blocked: the file export still works
  }
}

export function download(notebook: Notebook) {
  const blob = new Blob([JSON.stringify(notebook, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `${notebook.title || "notatnik"}.electro.json`;
  a.click();
  URL.revokeObjectURL(a.href);
}

export async function upload(file: File): Promise<Notebook> {
  const data = JSON.parse(await file.text());
  if (data?.version !== 1 || !Array.isArray(data.cells)) throw new Error("To nie jest plik notatnika.");
  return data;
}

/** A first notebook that shows every kind of cell. */
export function example(): Notebook {
  return {
    version: 1,
    title: "Sprawozdanie: mostek Wheatstone'a",
    codeInPdf: true,
    cells: [
      {
        id: newId(), type: "markdown",
        source: "## Cel ćwiczenia\n\nWyznaczyć nieznany opór $R_2$ z warunku równowagi mostka: amperomierz pokazuje $I_A = 0$.",
      },
      {
        id: newId(), type: "schematic", name: "mostek",
        schematic: {
          elements: [
            { id: "E_1", kind: "voltage_source", at: [0, 12], rotation: 270, value: "10", text: null },
            { id: "R_1", kind: "resistor", at: [4, 0], rotation: 90, value: "100", text: null },
            { id: "R_2", kind: "resistor", at: [4, 6], rotation: 90, value: null, text: null },
            { id: "R_3", kind: "resistor", at: [14, 0], rotation: 90, value: "50", text: null },
            { id: "R_4", kind: "resistor", at: [14, 6], rotation: 90, value: "100", text: null },
            { id: "A_1", kind: "ammeter", at: [7, 5], rotation: 0, value: null, text: null },
            { id: "gnd1", kind: "ground", at: [0, 12], rotation: 0, value: null, text: null },
          ],
          wires: [
            { points: [[0, 8], [0, 0], [4, 0]] }, { points: [[4, 0], [14, 0]] }, { points: [[4, 4], [4, 6]] },
            { points: [[14, 4], [14, 6]] },
            { points: [[4, 5], [7, 5]] }, { points: [[11, 5], [14, 5]] }, { points: [[4, 10], [4, 12]] },
            { points: [[14, 10], [14, 12]] }, { points: [[0, 12], [14, 12]] },
          ],
        },
      },
      {
        id: newId(), type: "code", outputs: [],
        source: 'mostek = schemat("mostek").to_circuit()\nsol = mostek.solve(I_A_1=0, find="R_2")\nsteps(sol)',
      },
      {
        id: newId(), type: "markdown",
        source: "## Wyniki\n\nSchemat z prądami i napięciami w równowadze:",
      },
      {
        id: newId(), type: "code", outputs: [],
        source: 'schematic(schemat("mostek"), mostek.solve(I_A_1=0))',
      },
      {
        id: newId(), type: "markdown",
        source: "Obwody można też pisać kodem — `+` szeregowo, `|` równolegle:",
      },
      {
        id: newId(), type: "code", outputs: [],
        source: "uklad = (VoltageSource(12) + Resistor(2)) | Resistor(4) | ((Resistor(6) | CurrentSource(1)) + VoltageSource(6).transpose())\nschematic(uklad, uklad.solve())",
      },
    ],
  };
}
