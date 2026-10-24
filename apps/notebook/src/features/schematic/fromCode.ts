// The code view edited back into a drawing: what the kernel made of the code (its problem as data) laid
// out by the series and parallel it is made of — or, when only values changed, the drawing as it was with
// the new values (its own layout kept).
import type { Failure } from "@/shared/model/issues";
import type { SchematicData, SymbolLibrary } from "@/shared/model/types";
import { SYMMETRIC, shapeOf } from "./code";
import { CannotLayOut, layout } from "./layout";
import { waveText } from "./model";
import { elementsOf, type NetlistElement } from "./problem";

export interface FromCode {
  netlist: { elements: NetlistElement[] };
  show?: string | null; // what the code shows after the circuit (code.ts: ``FINAL``)
}

const READINGS: Record<string, string> = { potentiometer: "position", photoresistor: "lux", thermistor: "temperature" };

/** What an element's parameters say, as a drawing writes it beside it (``problem.ts``'s ``read`` the
 *  other way): a part, a frequency and phase or duty, a switch's position, a reading. */
export function textOf(e: NetlistElement): string | null {
  const p = e.params ?? {};
  if (e.part) return e.part;
  if (e.kind === "sine_source") return waveText(String(p.f ?? "50"), 50, Number(p.phase ?? 0));
  if (e.kind === "square_source") return waveText(String(p.f ?? "1k"), Math.round(Number(p.duty ?? 0.5) * 100));
  if (e.kind === "switch" || e.kind === "button") return Number(p.closed ?? 0) ? "closed" : null;
  const reading = READINGS[e.kind];
  return reading && p[reading] !== undefined ? String(p[reading]) : null;
}

/** The same circuit: the same elements, of the same kinds, on the same points — whatever the points are
 *  called, and either way round for an element the same both ways (a resistor). Each point is known by what
 *  is on it: each element's id and which of its ends. */
function same(a: NetlistElement[], b: NetlistElement[]): boolean {
  const kinds = (x: NetlistElement[]) => JSON.stringify(x.map((e) => [e.id, e.kind]).sort());
  const points = (x: NetlistElement[]) => {
    const on = new Map<string, string[]>();
    for (const e of x)
      e.nodes.forEach((n, i) => on.set(n, [...(on.get(n) ?? []), `${e.id}:${SYMMETRIC.has(e.kind) ? "*" : i}`]));
    return JSON.stringify([...on.values()].map((ends) => ends.sort().join(" ")).sort());
  };
  return kinds(a) === kinds(b) && points(a) === points(b);
}

export function drawingFromCode(
  back: FromCode,
  old: SchematicData,
  lib: SymbolLibrary,
): { schematic: SchematicData } | { error: Failure } {
  if (old.parts && Object.keys(old.parts).length)
    return { error: { data: "PartsNotInCode", issue: { type: "PartsNotInCode" } } };
  const fresh = back.netlist.elements;
  if (same(elementsOf(old, lib).elements, fresh)) {
    const byId = new Map(fresh.map((e) => [e.id, e]));
    const elements = old.elements.map((e) => {
      const f = byId.get(e.id);
      return f ? { ...e, value: f.value ?? null, text: textOf(f) ?? e.text } : e;
    });
    return { schematic: { ...old, elements } };
  }
  const cause = { type: "CannotLayOut" as const, circuit: "" };
  const shape = shapeOf(fresh);
  if (!shape) return { error: { data: "OnlyValuesInCode", issue: { type: "OnlyValuesInCode", cause } } };
  try {
    return { schematic: layout(shape, fresh, textOf) };
  } catch (error) {
    if (error instanceof CannotLayOut)
      return { error: { data: "OnlyValuesInCode", issue: { type: "OnlyValuesInCode", cause } } };
    throw error;
  }
}
