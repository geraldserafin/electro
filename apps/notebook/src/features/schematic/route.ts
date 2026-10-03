// A wire laid from one point to another by itself: along the grid, around the elements, never along
// another wire or through a pin or a wire's end or corner (that would join what is not to be joined),
// with as few corners as it can. Crossing another wire is fine (lines that only cross are not joined).
import type { Point, SchematicData, SymbolLibrary } from "@/shared/model/types";
import { isComponent, key, pins, same } from "./model";

const BEND = 4; // a corner costs as much as this many squares of wire
const MARGIN = 6; // how far around the two ends it may go, in squares
const STEPS: Point[] = [
  [1, 0],
  [0, 1],
  [-1, 0],
  [0, -1],
];

const edge = (a: Point, b: Point) =>
  a[0] < b[0] || (a[0] === b[0] && a[1] < b[1]) ? `${key(a)}|${key(b)}` : `${key(b)}|${key(a)}`;

/** The squares a wire may not pass through, and the unit stretches it may not lie along. */
function obstacles(sch: SchematicData, lib: SymbolLibrary) {
  const blocked = new Set<string>();
  const along = new Set<string>();
  for (const e of sch.elements) {
    const ps = pins(e, lib);
    for (const p of ps) blocked.add(key(p));
    if (!isComponent(e.kind) || !ps.length) continue;
    // its body: between its two pins, or the box its pins make (a chip, a transistor)
    const [x0, x1] = [Math.min(...ps.map((p) => p[0])), Math.max(...ps.map((p) => p[0]))];
    const [y0, y1] = [Math.min(...ps.map((p) => p[1])), Math.max(...ps.map((p) => p[1]))];
    for (let x = x0; x <= x1; x++) for (let y = y0; y <= y1; y++) blocked.add(key([x, y]));
  }
  for (const w of sch.wires) {
    for (const p of w.points) blocked.add(key(p));
    for (let i = 0; i + 1 < w.points.length; i++) {
      const [a, b] = [w.points[i]!, w.points[i + 1]!];
      const d: Point = [Math.sign(b[0] - a[0]), Math.sign(b[1] - a[1])];
      for (let p = a; !same(p, b); ) {
        const q: Point = [p[0] + d[0], p[1] + d[1]];
        along.add(edge(p, q));
        p = q;
      }
    }
  }
  return { blocked, along };
}

/** The wire from ``a`` to ``b`` (both ends as they are, whatever is there): its corners. Nowhere to go
 *  around: ``fallback`` (a plain elbow). ``out``: the way it would rather leave ``a`` (out of a pin, along
 *  its element — of two ways alike, that one). */
export function route(
  sch: SchematicData,
  lib: SymbolLibrary,
  a: Point,
  b: Point,
  fallback: Point[],
  out?: Point,
): Point[] {
  if (same(a, b)) return [a];
  const { blocked, along } = obstacles(sch, lib);
  const box = [
    Math.min(a[0], b[0]) - MARGIN,
    Math.max(a[0], b[0]) + MARGIN,
    Math.min(a[1], b[1]) - MARGIN,
    Math.max(a[1], b[1]) + MARGIN,
  ];
  const free = (p: Point) =>
    p[0] >= box[0]! && p[0] <= box[1]! && p[1] >= box[2]! && p[1] <= box[3]! && (same(p, b) || !blocked.has(key(p)));

  // A* over (square, the way it came): its length and its corners
  type Node = { p: Point; dir: number; g: number; f: number; from: Node | null };
  const h = (p: Point) => Math.abs(p[0] - b[0]) + Math.abs(p[1] - b[1]) + (p[0] !== b[0] && p[1] !== b[1] ? BEND : 0);
  const open: Node[] = [{ p: a, dir: -1, g: 0, f: h(a), from: null }];
  const best = new Map<string, number>();
  let found: Node | null = null;
  while (open.length) {
    // ponytail: the cheapest by a scan — a few hundred squares in the box; a heap if boxes grow
    let i = 0;
    for (let k = 1; k < open.length; k++) if (open[k]!.f < open[i]!.f) i = k;
    const n = open.splice(i, 1)[0]!;
    if (same(n.p, b)) {
      found = n;
      break;
    }
    STEPS.forEach((d, dir) => {
      if (n.dir >= 0 && (dir + 2) % 4 === n.dir) return; // not straight back
      const p: Point = [n.p[0] + d[0], n.p[1] + d[1]];
      if (!free(p) || along.has(edge(n.p, p))) return;
      const g = n.g + 1 + (n.dir >= 0 && n.dir !== dir ? BEND : 0) + (n.dir < 0 && out && !same(d, out) ? 0.5 : 0);
      const id = `${key(p)}:${dir}`;
      if ((best.get(id) ?? Infinity) <= g) return;
      best.set(id, g);
      open.push({ p, dir, g, f: g + h(p), from: n });
    });
  }
  if (!found) return fallback;
  const path: Point[] = [];
  for (let n: Node | null = found; n; n = n.from) path.unshift(n.p);
  // only its corners
  return path.filter((p, k) => {
    if (k === 0 || k === path.length - 1) return true;
    const [q, r] = [path[k - 1]!, path[k + 1]!];
    return !((q[0] === p[0] && p[0] === r[0]) || (q[1] === p[1] && p[1] === r[1]));
  });
}
