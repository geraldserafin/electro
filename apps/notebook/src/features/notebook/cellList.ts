// The note's cells as a list: moving one, naming a new schematic. Pure, no React.
import type { Cell } from "@/shared/model/types";

/** ``cells`` with the one at ``index`` swapped with its neighbour ``by`` away (the same at the ends). */
export function moveCell(cells: Cell[], index: number, by: number): Cell[] {
  const target = index + by;
  if (target < 0 || target >= cells.length) return cells;
  const next = [...cells];
  [next[index], next[target]] = [next[target], next[index]];
  return next;
}

/** "Układ 1", "Układ 2", …: the first ``name(n)`` no schematic has yet. */
export function freeName(cells: Cell[], name: (n: number) => string): string {
  const taken = new Set(cells.flatMap((c) => (c.type === "schematic" ? [c.name] : [])));
  let n = 1;
  while (taken.has(name(n))) n++;
  return name(n);
}
