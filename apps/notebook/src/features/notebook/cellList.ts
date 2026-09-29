// The note's cells as a list: moving one, naming a new schematic. Pure, no React.
import type { Cell } from "@/shared/model/types";

/**
 * ``cells`` with ``count`` of them from ``from`` moved to stand before the one now at ``before``
 * (``cells.length``: at the end). Dropped inside itself: no change.
 */
export function moveRange(cells: Cell[], from: number, count: number, before: number): Cell[] {
  if (before >= from && before <= from + count) return cells;
  const moved = cells.slice(from, from + count);
  const rest = [...cells.slice(0, from), ...cells.slice(from + count)];
  const at = before > from ? before - count : before;
  return [...rest.slice(0, at), ...moved, ...rest.slice(at)];
}

/** "Układ 1", "Układ 2", …: the first ``name(n)`` no schematic has yet. */
export function freeName(cells: Cell[], name: (n: number) => string): string {
  const taken = new Set(cells.flatMap((c) => (c.type === "schematic" ? [c.name] : [])));
  let n = 1;
  while (taken.has(name(n))) n++;
  return name(n);
}
