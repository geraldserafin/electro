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
}

/** electro_render.symbol_library(): how every element kind looks. */
export interface SymbolLibrary {
  grid: number;
  style: string;
  kinds: Record<string, { pins: Point[]; svg: string; letter: string | null; upright: boolean }>;
}

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
