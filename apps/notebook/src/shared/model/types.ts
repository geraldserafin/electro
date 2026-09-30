import type { Failure, Issue, Steps } from "./issues";

export type Point = [number, number];

/** Mirrors electro_schematic.Element / Wire / Schematic (the JSON the Python side reads). */
export interface ElementData {
  id: string;
  kind: string;
  at: Point;
  rotation: number;
  value: string | null;
  text: string | null;
}

export interface WireData {
  points: Point[];
}

export interface SchematicData {
  elements: ElementData[];
  wires: WireData[];
  parts?: Record<string, PartDef>; // one's own components on it (kind "part", its text the key)
}

/** A pin of one's own component: its port's name, which side of the box, how far along it. */
export interface PartPin {
  name: string;
  side: "left" | "right" | "top" | "bottom";
  at: number; // grid squares from the top (left, right) or the left (top, bottom)
}

/** One's own component (electro_schematic.Part): a box of `size` grid squares, its pins sticking out
 *  a square from its sides, and inside a drawing whose ports are the pins. */
export interface PartDef {
  name: string;
  size: [number, number];
  pins: PartPin[];
  schematic: SchematicData;
  prefix?: string; // its elements' ids: U_1, U_2…
}

/** electro_render.symbol_library(): how every element kind looks. */
export interface SymbolLibrary {
  grid: number;
  style: string;
  kinds: Record<
    string,
    {
      pins: Point[];
      svg: string;
      letter: string | null;
      upright: boolean;
      leads?: Point[];
      box?: Point;
      parts?: string[];
    } // leads: from each pin into the body; box: a part's size (px); parts: real parts to choose (the element's ``text``)
  >;
  standards?: Record<string, Record<string, string>>; // per standard, the symbols it draws unlike the kinds' (IEC's)
}

/** The symbols' standard a note draws with: IEC 60617 (a box for a resistor) or IEEE 315 (a zigzag). */
export type SymbolStandard = "iec" | "ieee";

export type Output =
  | { type: "text" | "stream" | "svg" | "markdown"; data: string }
  | ({ type: "error" | "warning" } & Failure)
  | ({ type: "issue"; kind: "error" | "warning" } & Failure) // display(err): an issue shown on purpose
  | { type: "solution"; data: Steps }; // steps(sol)

/** What "Symuluj" found for one element (already formatted, e.g. "33.33 mA"). */
export interface ElementResult {
  value: string;
  solved: boolean; // the value was unknown (or a hole) and the solver found it
  U: string | null;
  I: string | null;
  P: string | null;
  reversed: boolean; // the current really flows from the second pin to the first
}

/** A warning (not everything could be found) or an error: our issue, else its text (older notes:
 *  the text alone, in Markdown). */
export interface Problem {
  kind: "warning" | "error";
  issue?: Issue;
  text?: string;
}

export type Cell =
  | { id: string; type: "markdown"; source: string }
  | { id: string; type: "code"; source: string; outputs: Output[]; execution?: number }
  | {
      id: string;
      type: "schematic";
      name: string;
      schematic: SchematicData;
      results?: Record<string, ElementResult>; // from the last run
      problems?: Problem[]; // why the last run could not find everything
      stale?: boolean; // the drawing changed since the last run
      frequency?: { svg: string; stale?: boolean }; // the last Bode plot (∿), and whether the drawing changed since
      view?: SchematicView; // which side of the cell is shown
    };

export type CellType = Cell["type"];

/** A schematic cell, while it is edited: as the board, or as code. */
export type SchematicView = "schematic" | "code";

/** A notebook file (*.electro.json), version 2 — see format.ts / electro_notes. */
export interface Notebook {
  format: "electro-notebook";
  version: 2;
  id: string; // stable identity, kept across saves
  title: string;
  created: string; // ISO 8601
  modified: string;
  settings: { codeInPdf: boolean; [key: string]: unknown };
  cells: Cell[];
  [key: string]: unknown; // keys a newer version wrote: kept as they are
}
