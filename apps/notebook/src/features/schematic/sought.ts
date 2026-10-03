// A drawing as a problem is set: the drawing defines the circuit, its data (each element's value, each
// mark's: an arrow's, a point's) are given apart from it, and what is sought is asked for — a quantity
// of an element, a point's potential, the resistance between two points. Kept in the drawing as keys
// (``find``), each the solver's (electro_notebook.kernel.simulate):
//   "U:R_5", "I:R_5", "P:R_5"  its voltage, current, power   "value:R_5"  its value
//   "mark:U1"                   what a mark (an arrow, a loop's current, a point's potential) is
//   "R:A:B"                     the resistance between points A and B (terminals, labels), as seen from there
import type { ElementData, SchematicData, SymbolLibrary } from "@/shared/model/types";
import { hasValue, isComponent, isMark, kindInfo, pins } from "./model";

/** A point the circuit has (a resistance between two of them, a potential): a terminal, a net label. */
export const isPoint = (kind: string) => kind === "terminal" || kind === "label";

/** What each of its elements is given as (its row in the data): a component with a value, a mark, a point. */
export const givenBy = (e: ElementData) => hasValue(e.kind) || isMark(e.kind) || isPoint(e.kind);

/** Its unit: an element's own, a voltage's and a potential's V, a current's A. */
export const unitOf = (e: ElementData) =>
  isComponent(e.kind)
    ? (kindInfo(e.kind)?.unit ?? "")
    : e.kind === "current_arrow" || e.kind === "mesh_current"
      ? "A"
      : "V";

/** How it is named on the drawing: a component by its label, a mark or a point by its name. */
export const nameOf = (e: ElementData) => (isComponent(e.kind) ? e.id : e.text || e.id);

/** What is sought: what was asked for, then what has no value given (an element's unknown, a mark's) — each once. */
export function sought(sch: SchematicData): string[] {
  const unknown = sch.elements.flatMap((e) =>
    givenBy(e) && !isPoint(e.kind) && !e.value?.trim() ? [isMark(e.kind) ? `mark:${e.id}` : `value:${e.id}`] : [],
  );
  const asked = (sch.find ?? []).filter((k) => named(sch, k) !== null);
  return [...new Set([...asked, ...unknown])];
}

/** A key's name as a book writes it ("U_R5", "R_AB", "I_2"): a base, ``_``, a subscript; null when what it
 *  is of is no longer on the drawing. */
export function named(sch: SchematicData, key: string): string | null {
  const [what, a, b] = key.split(":");
  const of = (id?: string) => sch.elements.find((e) => e.id === id);
  if (what === "R") {
    const [p, q] = [of(a), of(b)];
    return p && q ? `R_${nameOf(p)}${nameOf(q)}` : null;
  }
  const e = of(a);
  if (!e) return null;
  if (what === "value" || what === "mark") return nameOf(e);
  return `${what}_${e.id.replace(/_/g, "")}`;
}

/** What may be asked for on this drawing, by what it is: the elements (two-pin ones' voltage, current,
 *  power; any one's value), the points (their potential, two of them a resistance). */
export function askable(sch: SchematicData, lib: SymbolLibrary) {
  const two = sch.elements.filter((e) => isComponent(e.kind) && pins(e, lib).length === 2);
  return {
    elements: two,
    valued: sch.elements.filter((e) => isComponent(e.kind) && hasValue(e.kind)),
    points: sch.elements.filter((e) => isPoint(e.kind)),
  };
}
