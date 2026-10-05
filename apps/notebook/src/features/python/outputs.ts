// A code cell's run, both ways across the kernel: what it is given (each schematic cell's problem by its
// name, each kind's unit) and what it shows, made pictures here — a circuit laid out and drawn with the
// note's symbols, a plot drawn — so a note keeps them as it keeps any picture.
import {
  type BodeData,
  bodeSvg,
  type HistogramData,
  histogramSvg,
  type TraceData,
  traceSvg,
} from "@/features/plots/svg";
import { textOf } from "@/features/schematic/fromCode";
import { CannotLayOut, layout, type Shape } from "@/features/schematic/layout";
import { KINDS, type KindInfo } from "@/features/schematic/model";
import { pictureOf } from "@/features/schematic/picture";
import { type NetlistElement, problemOf } from "@/features/schematic/problem";
import type { ElementResult, Output, SchematicData, SymbolLibrary } from "@/shared/model/types";

/** What the kernel sends besides the outputs a note keeps: a circuit to draw, a plot. */
export type Shown =
  | Output
  | {
      type: "schematic";
      netlist: { elements: NetlistElement[] };
      shape: Shape | null;
      results?: Record<string, ElementResult>;
    }
  | { type: "plot"; trace?: TraceData; bode?: BodeData; histogram?: HistogramData };

/** The kernel's `run` arguments: each schematic cell's problem (one that cannot be read left out: the
 *  cells that use it say so), each kind's unit. */
export function given(schematics: Record<string, SchematicData>, lib: SymbolLibrary) {
  const problems: Record<string, unknown> = {};
  for (const [name, sch] of Object.entries(schematics)) {
    try {
      const { marks: _, ...data } = problemOf(sch, lib);
      problems[name] = data;
    } catch {}
  }
  const units = Object.fromEntries(KINDS.map((k): KindInfo => k).flatMap((k) => (k.unit ? [[k.kind, k.unit]] : [])));
  return { problems: JSON.stringify(problems), units: JSON.stringify(units) };
}

/** Each output as a note keeps it: a circuit drawn, a plot drawn; the rest as it is. */
export async function shown(outputs: Shown[], lib: SymbolLibrary): Promise<Output[]> {
  return Promise.all(outputs.map((o) => one(o, lib)));
}

async function one(o: Shown, lib: SymbolLibrary): Promise<Output> {
  if (o.type === "plot") {
    const svg = o.trace ? traceSvg(o.trace) : o.bode ? bodeSvg(o.bode) : histogramSvg(o.histogram!);
    return { type: "svg", data: svg };
  }
  if (o.type !== "schematic") return o;
  const elements = o.netlist.elements;
  try {
    if (o.shape) return { type: "svg", data: await pictureOf(layout(o.shape, elements, textOf), lib, o.results) };
  } catch (error) {
    if (!(error instanceof CannotLayOut)) throw error;
  }
  const line = (e: NetlistElement) => [e.id, e.kind, ...e.nodes, e.value ?? ""].join(" ").trim();
  return { type: "text", data: elements.map(line).join("\n") };
}
