// Editing helpers for the schematic JSON. They mirror electro_schematic.model
// (pins, rotation, wires following a moved element) so dragging needs no round trip
// to Python; connectivity and solving stay on the Python side.
import type { ElementData, Point, SchematicData, SymbolLibrary, WireData } from "@/shared/model/types";

export type KindGroup = "passive" | "sources" | "meters" | "connections" | "other";

/** What an element is, apart from its name (that is in messages.ts: kinds.<kind>). */
export interface KindInfo {
  kind: string;
  prefix: string;
  group: KindGroup; // section of the element library
  unit?: string;
  meter?: boolean; // the value is a reading: a measured datum, or left empty to be computed
}

export const KINDS = [
  { kind: "resistor", prefix: "R", unit: "Ω", group: "passive" },
  { kind: "capacitor", prefix: "C", unit: "F", group: "passive" },
  { kind: "inductor", prefix: "L", unit: "H", group: "passive" },
  { kind: "voltage_source", prefix: "E", unit: "V", group: "sources" },
  { kind: "current_source", prefix: "J", unit: "A", group: "sources" },
  { kind: "ammeter", prefix: "A", unit: "A", meter: true, group: "meters" },
  { kind: "voltmeter", prefix: "V", unit: "V", meter: true, group: "meters" },
  { kind: "ground", prefix: "gnd", group: "connections" },
  { kind: "label", prefix: "lbl", group: "connections" },
  { kind: "hole", prefix: "X", group: "other" },
  { kind: "opamp", prefix: "OA", group: "other" },
] as const satisfies readonly KindInfo[];

export type Kind = (typeof KINDS)[number]["kind"];

export const kindInfo = (kind: string): KindInfo | undefined => KINDS.find((k) => k.kind === kind);
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

export function simplify(points: Point[]): Point[] {
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

/**
 * Wires whose ends sat on a moved pin follow it. The last segment slides along with the
 * pin (as in CAD tools), so dragging never folds a wire back over itself or another wire.
 */
function drag(wires: WireData[], moved: Map<string, Point>): WireData[] {
  return wires.map((w) => {
    let pts = w.points;
    for (const end of [0, -1] as const) {
      const at = end === 0 ? pts[0] : pts[pts.length - 1];
      const target = moved.get(key(at));
      if (!target || same(target, at)) continue;
      const path = end === -1 ? [...pts] : [...pts].reverse();
      const n = path.length;
      const [prev, last] = [path[n - 2], path[n - 1]];
      if (n >= 3) {
        path[n - 2] = prev[1] === last[1] ? [prev[0], target[1]] : [target[0], prev[1]];
        path[n - 1] = target;
      } else path.splice(n - 1, 1, [target[0], prev[1]], target);
      const next = simplify(path);
      pts = end === -1 ? next : next.reverse();
    }
    return { points: pts };
  });
}

/**
 * Move a group by ``d``: its elements and the wires wholly inside it shift together;
 * other wires attached to the group's pins follow like when one element moves.
 */
export function moveGroup(
  sch: SchematicData, lib: SymbolLibrary, ids: string[], wireIndexes: number[], d: Point,
): SchematicData {
  const inGroup = new Set(ids);
  const shift = ([x, y]: Point): Point => [x + d[0], y + d[1]];
  const moved = new Map<string, Point>();
  const elements = sch.elements.map((e) => {
    if (!inGroup.has(e.id)) return e;
    pins(e, lib).forEach((p) => moved.set(key(p), shift(p)));
    return { ...e, at: shift(e.at) };
  });
  const own = new Set(wireIndexes);
  // wires hanging on the group's own wires follow them too, not only those on its pins
  sch.wires.forEach((w, i) => { if (own.has(i)) w.points.forEach((p) => moved.set(key(p), shift(p))); });
  // …including ends that sit in the middle of one of them (T-junctions)
  const groupWires = sch.wires.filter((_, i) => own.has(i));
  for (const w of sch.wires.filter((_, i) => !own.has(i)))
    for (const end of [w.points[0], w.points[w.points.length - 1]])
      if (groupWires.some((g) => g.points.slice(1).some((q, j) => onSegment(end, g.points[j], q))))
        moved.set(key(end), shift(end));
  const others = drag(sch.wires.filter((_, i) => !own.has(i)), moved);
  let next = 0;
  const wires = sch.wires.map((w, i) => (own.has(i) ? { points: w.points.map(shift) } : others[next++]));
  return { elements, wires };
}

/**
 * What a rubber band from a to b (drawing units) covers: elements and wires wholly inside.
 * A wire attached to an element left outside stays out of the group (it stretches instead),
 * so moving the group never tears it off that element.
 */
export function inBox(sch: SchematicData, lib: SymbolLibrary, a: Point, b: Point): { ids: string[]; wires: number[] } {
  const [x0, x1, y0, y1] = [Math.min(a[0], b[0]), Math.max(a[0], b[0]), Math.min(a[1], b[1]), Math.max(a[1], b[1])];
  const inside = ([x, y]: Point) => x >= x0 && x <= x1 && y >= y0 && y <= y1;
  const ids = sch.elements.filter((e) => pins(e, lib).every(inside)).map((e) => e.id);
  const chosen = new Set(ids);
  const outsidePins = new Set(sch.elements.filter((e) => !chosen.has(e.id)).flatMap((e) => pins(e, lib)).map(key));
  const wires = sch.wires.flatMap((w, i) => {
    const ends = [w.points[0], w.points[w.points.length - 1]];
    return w.points.every(inside) && !ends.some((p) => outsidePins.has(key(p))) ? [i] : [];
  });
  return { ids, wires };
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

/**
 * Connection rules (same as electro_schematic.Schematic.nodes): pins on the same point;
 * a wire end on a pin; a wire end that is not on a pin touching another wire (T-junction).
 * A wire passing over a pin, or crossing another wire, does not connect.
 */
function freeEnds(sch: SchematicData, lib: SymbolLibrary): Point[] {
  const pinKeys = new Set(sch.elements.filter((e) => e.kind !== "label").flatMap((e) => pins(e, lib)).map(key));
  return sch.wires.flatMap((w) => [w.points[0], w.points[w.points.length - 1]]).filter((p) => !pinKeys.has(key(p)));
}

const touchesWire = (p: Point, w: WireData) =>
  w.points.slice(1, -1).some((q) => same(q, p)) || w.points.slice(1).some((q, i) => onSegment(p, w.points[i], q));

/** How many connected things meet at each grid point (a wire counts twice where it passes). */
export function connections(sch: SchematicData, lib: SymbolLibrary): Map<string, number> {
  const count = new Map<string, number>();
  const bump = (p: Point, n: number) => count.set(key(p), (count.get(key(p)) ?? 0) + n);
  sch.elements.filter((e) => e.kind !== "label").flatMap((e) => pins(e, lib)).forEach((p) => bump(p, 1));
  sch.wires.forEach((w) => [w.points[0], w.points[w.points.length - 1]].forEach((p) => bump(p, 1)));
  for (const p of new Map(freeEnds(sch, lib).map((q) => [key(q), q])).values())
    for (const w of sch.wires) if (touchesWire(p, w)) bump(p, 2);
  return count;
}

/** Grid points where three or more wires/pins meet (drawn as dots). */
export function junctions(sch: SchematicData, lib: SymbolLibrary): Point[] {
  return [...connections(sch, lib).entries()].filter(([, n]) => n >= 3).map(([k]) => k.split(",").map(Number) as Point);
}

/** Pins with nothing attached (shown in red, so it is obvious what is not connected yet). */
export function openPins(sch: SchematicData, lib: SymbolLibrary): Point[] {
  const count = connections(sch, lib);
  return sch.elements
    .filter((e) => isComponent(e.kind))
    .flatMap((e) => pins(e, lib))
    .filter((p) => (count.get(key(p)) ?? 0) <= 1);
}

/**
 * A pin dropped onto the middle of a wire connects to it: the wire is split there.
 * Wires already attached to this element (dragged along with it) are left alone,
 * so they never short the element by running over its other pin.
 */
export function attach(sch: SchematicData, lib: SymbolLibrary, id: string): SchematicData {
  const element = sch.elements.find((e) => e.id === id);
  if (!element) return sch;
  const own = pins(element, lib);
  let wires = sch.wires;
  for (const p of own) {
    wires = wires.flatMap((w) => {
      const ends = [w.points[0], w.points[w.points.length - 1]];
      if (ends.some((end) => own.some((q) => same(q, end)))) return [w];
      for (let i = 0; i + 1 < w.points.length; i++)
        if (onSegment(p, w.points[i], w.points[i + 1]))
          return [{ points: [...w.points.slice(0, i + 1), p] }, { points: [p, ...w.points.slice(i + 1)] }];
      return [w];
    });
  }
  return wires === sch.wires ? sch : { ...sch, wires };
}

/** Is there something to connect to at p (a pin, a wire corner or end, or a wire body)? */
export function isConnectionPoint(sch: SchematicData, lib: SymbolLibrary, p: Point): boolean {
  if (sch.elements.some((e) => pins(e, lib).some((q) => same(q, p)))) return true;
  return sch.wires.some((w) => w.points.some((q) => same(q, p))
    || w.points.slice(1).some((q, i) => onSegment(p, w.points[i], q)));
}

/**
 * Move segment ``index`` of a wire sideways by ``by`` grid units (perpendicular to it).
 * Neighbouring segments stretch; the wire's ends stay where they are (a corner is added
 * next to them if needed), so its connections never change.
 */
export function moveSegment(w: WireData, index: number, by: number): WireData {
  const pts = w.points.map((p) => [...p] as Point);
  const [a, b] = [pts[index], pts[index + 1]];
  const shift = (p: Point): Point => (a[1] === b[1] ? [p[0], p[1] + by] : [p[0] + by, p[1]]);
  const moved = pts.map((p, i) => (i === index || i === index + 1 ? shift(p) : p));
  const path = [
    ...(index === 0 ? [pts[0]] : []),
    ...moved,
    ...(index + 1 === pts.length - 1 ? [pts[pts.length - 1]] : []),
  ];
  return { points: simplify(path) };
}

/** Where to put an element so that it rotates about its middle instead of its first pin. */
export function rotatedAbout(e: ElementData, lib: SymbolLibrary, rotation: number): Point {
  const middle = (el: ElementData) => {
    const ps = pins(el, lib);
    return [ps.reduce((s, p) => s + p[0], 0) / ps.length, ps.reduce((s, p) => s + p[1], 0) / ps.length];
  };
  const [bx, by] = middle(e);
  const [ax, ay] = middle({ ...e, rotation });
  return [e.at[0] + Math.round(bx - ax), e.at[1] + Math.round(by - ay)];
}

/** The L-shaped path from a to b (horizontal first). */
export function elbow(a: Point, b: Point): Point[] {
  return a[0] === b[0] || a[1] === b[1] ? [a, b] : [a, [b[0], a[1]], b];
}

export function bounds(sch: SchematicData, lib: SymbolLibrary): [number, number, number, number] {
  const pts = [...sch.elements.flatMap((e) => pins(e, lib)), ...sch.wires.flatMap((w) => w.points)];
  if (!pts.length) return [0, 0, 0, 0];
  const xs = pts.map((p) => p[0]);
  const ys = pts.map((p) => p[1]);
  return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
}
