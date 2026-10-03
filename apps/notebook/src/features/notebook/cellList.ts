// The note's cells as a list: moving one (or a section of the outline), naming a new schematic. Pure,
// no React.
import { newCell } from "@/shared/model/cells";
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

/** A place in the note: a cell, and a line of its text (a heading's; 0: the cell's start). */
export type Spot = { cell: string; line: number };

/**
 * ``cells`` with the section from ``from`` up to ``until`` moved to stand before ``before`` (``null``:
 * the note's end). A section starting, ending or landing within a text cuts it there, into two cells.
 * Dropped inside itself: no change.
 */
export function moveSection(cells: Cell[], from: Spot, until: Spot | null, before: Spot | null): Cell[] {
  const order = (s: Spot | null) => (s ? [cells.findIndex((c) => c.id === s.cell), s.line] : [cells.length, 0]);
  const cmp = (a: Spot | null, b: Spot | null) => {
    const [x, y] = [order(a), order(b)];
    return x[0]! - y[0]! || x[1]! - y[1]!;
  };
  if (cmp(before, from) >= 0 && cmp(before, until) <= 0) return cells;
  // the cuts, from the last line of a cell up (a cut leaves the lines above it where they were)
  const spots = [from, until, before].filter((s): s is Spot => !!s && s.line > 0);
  spots.sort((a, b) => -cmp(a, b));
  const made = new Map<string, string>(); // "cell:line" → the cell that starts there now
  let out = cells;
  for (const s of spots) {
    const key = `${s.cell}:${s.line}`;
    if (made.has(key)) continue;
    const i = out.findIndex((c) => c.id === s.cell);
    const cell = out[i];
    if (cell?.type !== "markdown") continue;
    const lines = cell.source.split("\n");
    const rest = { ...newCell("markdown"), source: lines.slice(s.line).join("\n") } as Cell;
    out = [
      ...out.slice(0, i),
      { ...cell, source: lines.slice(0, s.line).join("\n").trimEnd() },
      rest,
      ...out.slice(i + 1),
    ];
    made.set(key, rest.id);
  }
  const at = (s: Spot | null) => {
    if (!s) return out.length;
    const id = s.line > 0 ? (made.get(`${s.cell}:${s.line}`) ?? s.cell) : s.cell;
    return out.findIndex((c) => c.id === id);
  };
  const start = at(from);
  return moveRange(out, start, at(until) - start, at(before));
}
