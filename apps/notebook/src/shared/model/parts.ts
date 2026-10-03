/**
 * A note's chapters: its pages, one after another. A chapter starts at a text cell marked as such
 * (``"part": {}``), its first heading its name; what comes before the first one is a chapter too (the
 * note's start, named by its title). A note with no such cell is one chapter. The mark is a key of the
 * cell the format keeps as it is (any version reads it; the Python side passes it through).
 */

/** What starts a chapter, as a cell says it. */
export type PartMark = Record<string, never>;

type AnyCell = { readonly type: string; readonly id: string; readonly source?: string; readonly part?: unknown };

/** The cell's mark, if it starts a chapter. */
export const partMark = (cell: AnyCell): PartMark | null =>
  cell.type === "markdown" && typeof cell.part === "object" && cell.part !== null ? (cell.part as PartMark) : null;

/** A chapter: where it starts and ends (cells' indices, end not in it), its name (null: the note's
 *  title, for the start before any chapter). */
export interface Part {
  start: number;
  end: number;
  name: string | null;
}

/** The first heading of a text ("# Prawo Ohma" → "Prawo Ohma"), else its first line. */
const nameOf = (source: string) => {
  const lines = source.split("\n").filter((l) => l.trim());
  const heading = lines.find((l) => /^#{1,6}\s/.test(l));
  return (heading ?? lines[0] ?? "")
    .replace(/^#{1,6}\s+/, "")
    .replace(/[*_`]/g, "")
    .trim();
};

/** A note's chapters, in order (an empty start before the first marked one left out). */
export function partsOf(cells: readonly AnyCell[]): Part[] {
  const parts: Part[] = [];
  let current: Part = { start: 0, end: 0, name: null };
  cells.forEach((cell, i) => {
    if (!partMark(cell)) return;
    current.end = i;
    if (current.end > current.start || current.name !== null) parts.push(current);
    current = { start: i, end: i, name: nameOf(cell.source ?? "") };
  });
  current.end = cells.length;
  parts.push(current);
  return parts;
}
