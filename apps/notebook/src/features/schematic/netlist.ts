// A drawing as the circuit it shows: which pins and wires are one point (as KiCad has it), each point's
// name, every element between named points — the netlist electro reads (electro.core.problem.netlist) —
// and what each mark on it (an arrow, a loop's current, a point) is a quantity of.
import type { ElementData, Point, SchematicData, SymbolLibrary, WireData } from "@/shared/model/types";
import { isArrow, isComponent, key, onSegment, pins, rotate } from "./model";
import { withParts } from "./parts";

export const GROUND = "GND";

/** A quantity as electro reads it: of an element, of a point, between two, or a sum of them. */
export type Quantity =
  | ["I" | "U" | "P" | "value", string]
  | ["V", string]
  | ["U_between", string, string]
  | ["sum", [number, Quantity][]];

export interface NetElement {
  id: string;
  kind: string;
  value: string | null;
  text: string | null;
  nodes: string[];
}

export interface Netlist {
  elements: NetElement[];
  names: Map<string, string>; // a pin's or a wire's point (model.key) → the name of its point
}

class Groups {
  private parent = new Map<string, string>();
  find(x: string): string {
    if (!this.parent.has(x)) this.parent.set(x, x);
    let r = x;
    while (this.parent.get(r) !== r) r = this.parent.get(r)!;
    this.parent.set(x, r);
    return r;
  }
  union(a: string, b: string) {
    this.parent.set(this.find(a), this.find(b));
  }
}

const along = (p: Point, w: WireData) =>
  w.points.some((q) => q[0] === p[0] && q[1] === p[1]) || segments(w).some(([a, b]) => onSegment(p, a, b));

const segments = (w: WireData): [Point, Point][] => w.points.slice(1).map((b, i) => [w.points[i], b]);

/** Every pin's and wire's point → its point of the circuit (a representative). What joins: pins on one
 *  point; a wire's end on a pin; a wire's end on no pin touching another wire (its end, a corner, its
 *  middle); a terminal on the wire it lies on; labels (and ground) of one name. A wire only passing over a
 *  pin, or crossing another, does not. */
export function connected(sch: SchematicData, lib: SymbolLibrary): Map<string, string> {
  const library = withParts(lib, sch.parts);
  const groups = new Groups();
  const pinAt = new Map<string, string[]>();
  for (const e of sch.elements)
    pins(e, library).forEach((p, i) => {
      const k = key(p);
      pinAt.set(k, [...(pinAt.get(k) ?? []), `pin:${e.id}:${i}`]);
    });
  for (const keys of pinAt.values()) for (const k of keys) groups.union(k, keys[0]);
  sch.wires.forEach((w, i) => {
    groups.find(`wire:${i}`);
    for (const end of [w.points[0], w.points[w.points.length - 1]]) {
      const on = pinAt.get(key(end));
      if (on) groups.union(`wire:${i}`, on[0]);
    }
  });
  sch.wires.forEach((w, i) => {
    for (const end of [w.points[0], w.points[w.points.length - 1]]) {
      if (pinAt.has(key(end))) continue;
      sch.wires.forEach((v, j) => {
        if (j !== i && along(end, v)) groups.union(`wire:${i}`, `wire:${j}`);
      });
    }
  });
  for (const e of sch.elements) {
    if (e.kind !== "terminal") continue;
    const [p] = pins(e, library);
    sch.wires.forEach((w, i) => {
      if (along(p, w)) groups.union(`wire:${i}`, pinAt.get(key(p))![0]);
    });
  }
  const byName = new Map<string, string>();
  for (const e of sch.elements) {
    const name = e.kind === "ground" ? GROUND : e.kind === "label" || e.kind === "port" ? e.text : null;
    if (!name) continue;
    const k = pinAt.get(key(pins(e, library)[0]))![0];
    if (byName.has(name)) groups.union(k, byName.get(name)!);
    else byName.set(name, k);
  }
  const out = new Map<string, string>();
  for (const [p, keys] of pinAt) out.set(p, groups.find(keys[0]));
  sch.wires.forEach((w, i) => {
    for (const p of w.points) if (!out.has(key(p))) out.set(key(p), groups.find(`wire:${i}`));
  });
  return out;
}

export class UnknownPart extends Error {
  constructor(readonly part: string) {
    super(`UnknownPart: ${part}`);
  }
}

export class PartInItself extends Error {
  constructor(readonly part: string) {
    super(`PartInItself: ${part}`);
  }
}

/** The drawing as a netlist: its elements (one's own components opened up, their insides' ids
 *  prefixed by the part's) between named points — ground ``GND``, a label's or a port's text, a terminal
 *  its id, the rest ``n1``, ``n2``… */
export function netlist(sch: SchematicData, lib: SymbolLibrary): Netlist {
  return opened(sch, lib, "", null, []);
}

function opened(
  sch: SchematicData,
  lib: SymbolLibrary,
  prefix: string,
  outside: Map<string, string> | null,
  within: string[],
): Netlist {
  const library = withParts(lib, sch.parts);
  const point = connected(sch, lib);
  const names = new Map<string, string>();
  const nameOnce = (root: string, name: string) => {
    if (!names.has(root)) names.set(root, name);
  };
  const at = (e: ElementData) => point.get(key(pins(e, library)[0]))!;
  for (const e of sch.elements) if (e.kind === "ground") nameOnce(at(e), GROUND);
  if (outside)
    for (const e of sch.elements)
      if (e.kind === "port" && e.text && outside.has(e.text)) nameOnce(at(e), outside.get(e.text)!);
  for (const e of sch.elements)
    if ((e.kind === "label" || e.kind === "port") && e.text) nameOnce(at(e), prefix + e.text);
  for (const e of sch.elements) if (e.kind === "terminal") nameOnce(at(e), prefix + e.id);
  const taken = new Set(names.values());
  let k = 0;
  const name = (p: Point) => {
    const root = point.get(key(p))!;
    if (!names.has(root)) {
      do k++;
      while (taken.has(`${prefix}n${k}`));
      names.set(root, `${prefix}n${k}`);
      taken.add(`${prefix}n${k}`);
    }
    return names.get(root)!;
  };
  const elements: NetElement[] = [];
  for (const e of sch.elements) {
    if (e.kind === "part") {
      const def = sch.parts?.[e.text ?? ""];
      if (!def) throw new UnknownPart(e.text ?? "");
      if (within.includes(e.text ?? "") || within.length > 16) throw new PartInItself(e.text ?? "");
      const ports = new Map(def.pins.map((pin, i) => [pin.name, name(pins(e, library)[i])]));
      elements.push(...opened(def.schematic, lib, `${prefix}${e.id}_`, ports, [...within, e.text ?? ""]).elements);
    } else if (isComponent(e.kind)) {
      elements.push({
        id: prefix + e.id,
        kind: e.kind,
        value: e.value,
        text: e.text,
        nodes: pins(e, library).map(name),
      });
    }
  }
  const out = new Map<string, string>();
  for (const [p, root] of point) if (names.has(root)) out.set(p, names.get(root)!);
  return { elements, names: out };
}

/** The name of the point ``p`` is on: a pin, a wire's point or anywhere along a wire; null: on nothing. */
export function nodeAt(sch: SchematicData, names: Map<string, string>, p: Point): string | null {
  const found = names.get(key(p));
  if (found) return found;
  const w = sch.wires.find((w) => segments(w).some(([a, b]) => onSegment(p, a, b)));
  return w ? (names.get(key(w.points[0])) ?? null) : null;
}

/** How an arrow's quantity is the element's own (its current from its first pin to its second, its
 *  voltage V₁ − V₂): 1, −1, or null when its direction says nothing of it. Along the element: a current's
 *  the way it points, a voltage's head at the higher potential. Across it (a current's on a wire into it):
 *  into the element at its nearer pin, or out of it. */
export function arrowSign(arrow: ElementData, of: ElementData, lib: SymbolLibrary): number | null {
  const ps = pins(of, lib);
  if (ps.length !== 2) return null;
  const [[ax, ay], [bx, by]] = ps;
  const [dx, dy] = rotate([1, 0], arrow.rotation);
  const forward = dx * (bx - ax) + dy * (by - ay);
  if (forward) {
    const same = forward > 0 ? 1 : -1;
    return arrow.kind === "current_arrow" ? same : -same;
  }
  if (arrow.kind !== "current_arrow") return null;
  const tail = arrow.at;
  const head: Point = [tail[0] + dx, tail[1] + dy];
  const middle: Point = [(tail[0] + head[0]) / 2, (tail[1] + head[1]) / 2];
  const far = (p: Point, q: Point) => Math.abs(p[0] - q[0]) + Math.abs(p[1] - q[1]);
  const near = far(middle, ps[0]) <= far(middle, ps[1]) ? ps[0] : ps[1];
  const into = far(head, near) < far(tail, near);
  return (near === ps[0] ? 1 : -1) * (into ? 1 : -1);
}

const sum = (terms: Record<string, number>): Quantity => [
  "sum",
  Object.entries(terms).map(([id, k]) => [k, ["I", id]] as [number, Quantity]),
];

/** What each mark is a quantity of: a voltage arrow between two points V_head − V_tail; an arrow of an
 *  element its current or voltage, as it points; a current's arrow on a wire the current along it; a
 *  loop's arrow its mesh current; a terminal or a named label its point's potential. Marks that say
 *  nothing (on no wire, wires in a loop) are left out. */
export function quantities(sch: SchematicData, lib: SymbolLibrary, names: Map<string, string>) {
  const library = withParts(lib, sch.parts);
  const byId = new Map(sch.elements.map((e) => [e.id, e]));
  const potential = (p: Point): Quantity => ["V", nodeAt(sch, names, p) ?? GROUND];
  const out: [ElementData, Quantity][] = [];
  for (const a of sch.elements) {
    if (a.kind === "voltage_arrow" && a.between?.length === 2) {
      const [tail, head] = a.between.map((p) => nodeAt(sch, names, p) ?? GROUND);
      out.push([a, ["U_between", head, tail]]);
    } else if (isArrow(a.kind) && a.of) {
      const of = byId.get(a.of);
      const sign = of && isComponent(of.kind) && of.kind !== "part" ? arrowSign(a, of, library) : null;
      if (sign !== null) out.push([a, ["sum", [[sign, [a.kind === "current_arrow" ? "I" : "U", of!.id]]]]]);
    } else if (a.kind === "current_arrow" && !a.between) {
      const terms = currentAlong(sch, lib, a.at, rotate([1, 0], a.rotation));
      if (terms) out.push([a, sum(terms)]);
    } else if (a.kind === "mesh_current") {
      const terms = meshCurrent(sch, lib, a.at);
      if (terms) out.push([a, sum(Object.fromEntries(Object.entries(terms).map(([id, k]) => [id, a.flip ? -k : k])))]);
    } else if (a.kind === "terminal" || (a.kind === "label" && a.text)) {
      out.push([a, potential(a.at)]);
    }
  }
  return out;
}

/** The current along a wire at ``at`` the way ``step`` goes (a unit step along it): by Kirchhoff, what
 *  leaves the point beyond through its elements — ``{id: ±1}``, 1 for one it goes into by its first pin.
 *  null: no wire there; the wire's two sides joined some other way too; or an element of more than two
 *  pins beyond. */
export function currentAlong(
  sch: SchematicData,
  lib: SymbolLibrary,
  at: Point,
  step: Point,
): Record<string, number> | null {
  const head: Point = [at[0] + step[0], at[1] + step[1]];
  const on = (p: Point, a: Point, b: Point) =>
    (p[0] === a[0] && p[1] === a[1]) || (p[0] === b[0] && p[1] === b[1]) || onSegment(p, a, b);
  const found = sch.wires
    .flatMap((w, i) => segments(w).map(([a, b], k) => ({ i, k, a, b })))
    .find(({ a, b }) => on(at, a, b) && on(head, a, b));
  if (!found) return null;
  const { i, k } = found;
  const w = sch.wires[i];
  const [a, b] = [w.points[k], w.points[k + 1]];
  const forward = (b[0] - a[0]) * step[0] + (b[1] - a[1]) * step[1] > 0;
  const [first, second] = forward ? [at, head] : [head, at];
  const unique = (ps: Point[]) => ps.filter((p, j) => !j || p[0] !== ps[j - 1][0] || p[1] !== ps[j - 1][1]);
  const pieces = [unique([...w.points.slice(0, k + 1), first]), unique([second, ...w.points.slice(k + 1)])]
    .filter((ps) => ps.length > 1)
    .map((points) => ({ points }));
  const cut = { ...sch, wires: [...sch.wires.slice(0, i), ...pieces, ...sch.wires.slice(i + 1)] };
  const point = connected(cut, lib);
  if (!point.has(key(at))) return {};
  const beyond = point.get(key(head));
  if (point.get(key(at)) === beyond) return null;
  const library = withParts(lib, sch.parts);
  const out: Record<string, number> = {};
  for (const e of sch.elements) {
    if (!isComponent(e.kind)) continue;
    const ps = pins(e, library);
    for (const [j, p] of ps.entries()) {
      if (point.get(key(p)) !== beyond) continue;
      if (ps.length !== 2 || e.kind === "part") return null;
      out[e.id] = (out[e.id] ?? 0) + (j === 0 ? 1 : -1);
    }
  }
  return Object.fromEntries(Object.entries(out).filter(([, n]) => n));
}

type Edge = [Point, Point, ["wire"] | ["element", string] | null];

/** The drawing as a plane graph: a wire's stretches between the points something is at, each two-pin
 *  element's body from its first pin to its second, an element of more pins each pin to its middle (no
 *  one current there). null: wires crossing (not a plane). */
function plane(sch: SchematicData, lib: SymbolLibrary): Edge[] | null {
  const library = withParts(lib, sch.parts);
  const points: Point[] = [...sch.wires.flatMap((w) => w.points), ...sch.elements.flatMap((e) => pins(e, library))];
  const all = sch.wires.flatMap(segments);
  for (const [a, b] of all)
    for (const [c, d] of all)
      if (a[1] === b[1] && c[0] === d[0] && onSegment([c[0], a[1]], a, b) && onSegment([c[0], a[1]], c, d)) return null;
  const edges = new Map<string, Edge>();
  const add = (edge: Edge) => edges.set(JSON.stringify(edge), edge);
  for (const [a, b] of all) {
    const on = points
      .filter((p) => (p[0] === a[0] && p[1] === a[1]) || (p[0] === b[0] && p[1] === b[1]) || onSegment(p, a, b))
      .sort((p, q) => Math.abs(p[0] - a[0]) + Math.abs(p[1] - a[1]) - (Math.abs(q[0] - a[0]) + Math.abs(q[1] - a[1])));
    for (let j = 1; j < on.length; j++) {
      const [p, q] = [on[j - 1], on[j]];
      if (p[0] === q[0] && p[1] === q[1]) continue;
      const [lo, hi] = p[0] < q[0] || (p[0] === q[0] && p[1] < q[1]) ? [p, q] : [q, p];
      add([lo, hi, ["wire"]]);
    }
  }
  for (const e of sch.elements) {
    if (!isComponent(e.kind)) continue;
    const ps = pins(e, library);
    if (ps.length === 2 && e.kind !== "part") add([ps[0], ps[1], ["element", e.id]]);
    else if (ps.length > 1) {
      const middle: Point = [
        ps.reduce((s, p) => s + p[0], 0) / ps.length,
        ps.reduce((s, p) => s + p[1], 0) / ps.length,
      ];
      for (const p of ps) add([p, middle, null]);
    }
  }
  return [...edges.values()].sort((a, b) => (order(a) < order(b) ? -1 : order(a) > order(b) ? 1 : 0));
}

/** An edge as Python writes it, ``((0, 0), (0, 8), ('wire',))``: the edges in one order on both sides. */
function order([u, v, tag]: Edge): string {
  const p = ([x, y]: Point) => `(${x}, ${y})`;
  const t = tag === null ? "None" : tag.length === 1 ? "('wire',)" : `('element', '${tag[1]}')`;
  return `(${p(u)}, ${p(v)}, ${t})`;
}

/** The mesh current of the loop ``at`` is in — the smallest one drawn around it — clockwise on screen:
 *  ``{id: ±1}`` as ``currentAlong``. Each loop's current is the one around the loop next to it (outside
 *  the drawing: none) and the current of what is between them, the way it goes around: found so from
 *  outside in. null: in no loop, wires crossing, or only through what has no one current. */
export function meshCurrent(sch: SchematicData, lib: SymbolLibrary, at: Point): Record<string, number> | null {
  const edges = plane(sch, lib);
  if (!edges) return null;
  const half = [...edges.map(([u, v, t]): Edge => [u, v, t]), ...edges.map(([u, v, t]): Edge => [v, u, t])];
  const n = edges.length;
  const twin = (h: number) => (h + n) % (2 * n);
  const out = new Map<string, number[]>();
  half.forEach(([u], h) => out.set(key(u), [...(out.get(key(u)) ?? []), h]));
  for (const [, hs] of out)
    hs.sort((g, h) => {
      const angle = (x: number) => Math.atan2(half[x][1][1] - half[x][0][1], half[x][1][0] - half[x][0][0]);
      return angle(g) - angle(h);
    });
  const next = half.map(([, v], h) => {
    const hs = out.get(key(v))!;
    return hs[(hs.indexOf(twin(h)) - 1 + hs.length) % hs.length];
  });
  const faceOf = new Array<number>(2 * n).fill(-1);
  const faces: [number[], number][] = [];
  for (let h = 0; h < 2 * n; h++) {
    if (faceOf[h] >= 0) continue;
    const face: number[] = [];
    let g = h;
    while (faceOf[g] < 0) {
      faceOf[g] = faces.length;
      face.push(g);
      g = next[g];
    }
    const area = face.reduce((s, g) => s + half[g][0][0] * half[g][1][1] - half[g][1][0] * half[g][0][1], 0) / 2;
    faces.push([face, area]);
  }
  if (!faces.length) return null;
  const outer = Math.sign(faces.reduce((best, f) => (Math.abs(f[1]) > Math.abs(best[1]) ? f : best))[1]);
  const bounded = faces.flatMap(([, area], i) => (area && Math.sign(area) !== outer ? [i] : []));
  const inside = (face: number[]) =>
    face.filter((g) => {
      const [[x1, y1], [x2, y2]] = half[g];
      return y1 > at[1] !== y2 > at[1] && at[0] < x1 + ((at[1] - y1) * (x2 - x1)) / (y2 - y1);
    }).length %
      2 ===
    1;
  const around = bounded.filter((i) => inside(faces[i][0]));
  if (!around.length) return null;
  const target = around.reduce((best, i) => (Math.abs(faces[i][1]) < Math.abs(faces[best][1]) ? i : best));
  const sense = -outer;
  const library = withParts(lib, sch.parts);
  const currentOf = (h: number): Record<string, number> | null => {
    const [u, v, tag] = half[h];
    if (!tag) return null;
    if (tag[0] === "element") {
      const first = pins(sch.elements.find((e) => e.id === tag[1])!, library)[0];
      return { [tag[1]]: u[0] === first[0] && u[1] === first[1] ? 1 : -1 };
    }
    return currentAlong(sch, lib, u, [Math.sign(v[0] - u[0]), Math.sign(v[1] - u[1])]);
  };
  const known = new Map<number, Record<string, number>>();
  faces.forEach((_, i) => {
    if (!bounded.includes(i)) known.set(i, {});
  });
  const queue = [...known.keys()];
  while (queue.length && !known.has(target)) {
    const f = queue.shift()!;
    for (const h of faces[f][0]) {
      const g = faceOf[twin(h)];
      if (known.has(g)) continue;
      const current = currentOf(twin(h));
      if (!current) continue;
      const total = { ...known.get(f)! };
      for (const [id, k] of Object.entries(current)) total[id] = (total[id] ?? 0) + sense * k;
      known.set(g, Object.fromEntries(Object.entries(total).filter(([, k]) => k)));
      queue.push(g);
    }
  }
  return known.get(target) ?? null;
}
