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

export type Output = {
  type: "text" | "stream" | "svg" | "markdown" | "error" | "warning";
  data: string;
};

/** What "Symuluj" found for one element (already formatted, e.g. "33.33 mA"). */
export interface ElementResult {
  value: string;
  solved: boolean; // the value was unknown (or a hole) and the solver found it
  U: string | null;
  I: string | null;
  P: string | null;
  reversed: boolean; // the current really flows from the second pin to the first
}

export type Cell =
  | { id: string; type: "markdown"; source: string }
  | { id: string; type: "code"; source: string; outputs: Output[]; execution?: number }
  | {
      id: string;
      type: "schematic";
      name: string;
      schematic: SchematicData;
      data?: string; // measurements for the simulation, e.g. "I_A_1 = 0; U_R_2 = 4"
      results?: Record<string, ElementResult>;
      outputs?: Output[];
      stale?: boolean; // the drawing changed since the last simulation
    };

export type CellType = Cell["type"];

export interface Notebook {
  version: 1;
  title: string;
  codeInPdf: boolean;
  cells: Cell[];
}
