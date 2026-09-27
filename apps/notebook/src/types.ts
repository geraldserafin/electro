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

export type Cell =
  | { id: string; type: "markdown"; source: string }
  | { id: string; type: "code"; source: string; outputs: Output[] }
  | { id: string; type: "schematic"; name: string; schematic: SchematicData };

export type CellType = Cell["type"];

export interface Notebook {
  version: 1;
  title: string;
  codeInPdf: boolean;
  cells: Cell[];
}
