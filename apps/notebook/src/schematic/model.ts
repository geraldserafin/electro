// Editing helpers for the schematic JSON. They mirror electro_schematic.model
// (pins, rotation, wires following a moved element) so dragging needs no round trip
// to Python; connectivity and solving stay on the Python side.
import type { ElementData, Point, SchematicData, SymbolLibrary, WireData } from "../types";

export const KINDS: { kind: string; name: string; prefix: string; unit?: string }[] = [
  { kind: "resistor", name: "Rezystor", prefix: "R", unit: "Ω" },
  { kind: "voltage_source", name: "Źródło napięcia", prefix: "E", unit: "V" },
  { kind: "current_source", name: "Źródło prądu", prefix: "J", unit: "A" },
  { kind: "capacitor", name: "Kondensator", prefix: "C", unit: "F" },
  { kind: "inductor", name: "Cewka", prefix: "L", unit: "H" },
  { kind: "ammeter", name: "Amperomierz", prefix: "A" },
  { kind: "voltmeter", name: "Woltomierz", prefix: "V" },
  { kind: "hole", name: "Nieznany element", prefix: "X" },
  { kind: "opamp", name: "Wzmacniacz op.", prefix: "OA" },
  { kind: "ground", name: "Masa", prefix: "gnd" },
  { kind: "label", name: "Etykieta węzła", prefix: "lbl" },
];

export const kindInfo = (kind: string) => KINDS.find((k) => k.kind === kind);
export const hasValue = (kind: string) => kindInfo(kind)?.unit !== undefined;
export const isComponent = (kind: string) => !["ground", "label", "terminal"].includes(kind);

export const key = ([x, y]: Point) => `${x},${y}`;
export const same = (a: Point, b: Point) => a[0] === b[0] && a[1] === b[1];

export function rotate([x, y]: Point, rotation: number): Point {
  for (let i = 0; i < ((rotation / 90) % 4 + 4) % 4; i++) [x, y] = [-y, x];
  return [x, y];
}

export function pins(e: ElementData, lib: SymbolLibrary): Point[] {
  return lib.kinds[e.kind].pins.map(([px, py]) => {
    const [dx, dy] = rotate([px / lib.grid, py / lib.grid], e.rotation);
    return [e.at[0] + dx, e.at[1] + dy];
  });
}

/** Strictly inside the axis-aligned segment a–b? */
export function onSegment([x, y]: Point, [x1, y1]: Point, [x2, y2]: Point): boolean {
  if (x1 === x2 && x2 === x) return Math.min(y1, y2) < y && y < Math.max(y1, y2);
  if (y1 === y2 && y2 === y) return Math.min(x1, x2) < x && x < Math.max(x1, x2);
  return false;
}

export function nextId(sch: SchematicData, kind: string): string {
  const prefix = kindInfo(kind)?.prefix ?? kind;
  const sep = isComponent(kind) ? "_" : "";
  const used = sch.elements
    .map((e) => e.id.match(new RegExp(`^${prefix}${sep}(\\d+)$`)))
    .map((m) => (m ? Number(m[1]) : 0));
  return `${prefix}${sep}${Math.max(0, ...used) + 1}`;
}

function simplify(points: Point[]): Point[] {
  const out: Point[] = [];
  for (const p of points) {
    if (out.length && same(out[out.length - 1], p)) continue;
    if (out.length >= 2) {
      const [a, b] = [out[out.length - 2], out[out.length - 1]];
      if ((a[0] === b[0] && b[0] === p[0]) || (a[1] === b[1] && b[1] === p[1])) {
        out[out.length - 1] = p;
        continue;
      }
    }
    out.push(p);
  }
  return out;
}

/** Wires whose ends sat on a moved pin follow it, with an elbow to stay horizontal/vertical. */
function drag(wires: WireData[], moved: Map<string, Point>): WireData[] {
  return wires.map((w) => {
    let pts = w.points;
    for (const end of [0, -1] as const) {
      const at = end === 0 ? pts[0] : pts[pts.length - 1];
      const target = moved.get(key(at));
      if (!target || same(target, at)) continue;
      const path = end === -1 ? [...pts] : [...pts].reverse();
      const last = path[path.length - 1];
      const prev = path[path.length - 2];
      const elbow: Point = prev[0] === last[0] ? [prev[0], target[1]] : [target[0], prev[1]];
      const next = simplify([...path.slice(0, -1), elbow, target]);
      pts = end === -1 ? next : next.reverse();
    }
    return { points: pts };
  });
}

export function updateElement(
  sch: SchematicData, lib: SymbolLibrary, id: string, change: Partial<ElementData>,
): SchematicData {
  const old = sch.elements.find((e) => e.id === id);
  if (!old) return sch;
  const updated = { ...old, ...change };
  const before = pins(old, lib);
  const after = pins(updated, lib);
  const moved = new Map(before.map((p, i) => [key(p), after[i]] as const));
  return {
    elements: sch.elements.map((e) => (e.id === id ? updated : e)),
    wires: drag(sch.wires, moved),
  };
}

/** Grid points where three or more wires/pins meet (drawn as dots). */
export function junctions(sch: SchematicData, lib: SymbolLibrary): Point[] {
  const count = new Map<string, number>();
  const bump = (p: Point, n: number) => count.set(key(p), (count.get(key(p)) ?? 0) + n);
  const pinPoints = sch.elements.filter((e) => e.kind !== "label").flatMap((e) => pins(e, lib));
  const ends: Point[] = [];
  for (const w of sch.wires) {
    ends.push(w.points[0], w.points[w.points.length - 1]);
    bump(w.points[0], 1);
    bump(w.points[w.points.length - 1], 1);
    w.points.slice(1, -1).forEach((p) => bump(p, 2));
  }
  pinPoints.forEach((p) => bump(p, 1));
  const touching = [...new Map([...ends, ...pinPoints].map((p) => [key(p), p])).values()];
  for (const w of sch.wires)
    for (let i = 0; i + 1 < w.points.length; i++)
      for (const p of touching) if (onSegment(p, w.points[i], w.points[i + 1])) bump(p, 2);
  return [...count.entries()].filter(([, n]) => n >= 3).map(([k]) => k.split(",").map(Number) as Point);
}

export function bounds(sch: SchematicData, lib: SymbolLibrary): [number, number, number, number] {
  const pts = [...sch.elements.flatMap((e) => pins(e, lib)), ...sch.wires.flatMap((w) => w.points)];
  if (!pts.length) return [0, 0, 0, 0];
  const xs = pts.map((p) => p[0]);
  const ys = pts.map((p) => p[1]);
  return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
}
