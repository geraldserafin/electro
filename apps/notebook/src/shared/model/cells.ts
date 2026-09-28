import type { Cell, CellType } from "./types";

export const newId = () => Math.random().toString(36).slice(2, 10);

export function newCell(type: CellType): Cell {
  if (type === "markdown") return { id: newId(), type, source: "" };
  if (type === "code") return { id: newId(), type, source: "", outputs: [] };
  return { id: newId(), type, name: "uklad", schematic: { elements: [], wires: [] } };
}
