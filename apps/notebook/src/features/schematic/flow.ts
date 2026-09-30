// Where the current goes along the wires, for the moving dots while the circuit runs (as
// EveryCircuit draws it). The simulation knows each element's terminals' currents; a node's wires
// are a little network of their own (segments between the points where wires meet), and what flows
// along each segment follows from what goes in and out at the pins (Kirchhoff's law at each point).
// Where it cannot say — a ground, a net label (the current goes on elsewhere), a pin whose current is
// not known — the point takes whatever is left. A node's wires are a tree nearly always, so this is
// exact; a loop of wires shares it out as equal resistances would.
import type { Point, SchematicData, SymbolLibrary } from "@/shared/model/types";
import { pins } from "./model";

/** A wire's piece between two points where something meets (px). */
export interface Segment {
  a: Point;
  b: Point;
}

/** The wires' network, worked out once for a drawing and its nodes: each frame only its currents change. */
export interface FlowGraph {
  segments: Segment[];
  ends: [number, number][]; // each segment's two points (indices)
  inputs: { id: string; pin: number; at: number }[]; // a pin's current, into the network at a point
  groups: { free: number[]; inverse: Float64Array }[]; // each connected piece: its points not held at 0, L⁻¹ over them
  count: number; // points
}

const onSegment = (p: Point, a: Point, b: Point) =>
  (a[0] === b[0] && p[0] === a[0] && p[1] > Math.min(a[1], b[1]) && p[1] < Math.max(a[1], b[1])) ||
  (a[1] === b[1] && p[1] === a[1] && p[0] > Math.min(a[0], b[0]) && p[0] < Math.max(a[0], b[0]));

/** ``A⁻¹`` (n×n, row by row); null: singular. */
function invert(A: Float64Array, n: number): Float64Array | null {
  const M = Float64Array.from(A);
  const inv = new Float64Array(n * n);
  for (let i = 0; i < n; i++) inv[i * n + i] = 1;
  for (let col = 0; col < n; col++) {
    let pivot = col;
    for (let r = col + 1; r < n; r++) if (Math.abs(M[r * n + col]) > Math.abs(M[pivot * n + col])) pivot = r;
    if (Math.abs(M[pivot * n + col]) < 1e-12) return null;
    for (const X of [M, inv])
      for (let j = 0; j < n; j++) {
        const t = X[col * n + j];
        X[col * n + j] = X[pivot * n + j];
        X[pivot * n + j] = t;
      }
    const d = 1 / M[col * n + col];
    for (let j = 0; j < n; j++) {
      M[col * n + j] *= d;
      inv[col * n + j] *= d;
    }
    for (let r = 0; r < n; r++) {
      const f = M[r * n + col];
      if (r === col || f === 0) continue;
      for (let j = 0; j < n; j++) {
        M[r * n + j] -= f * M[col * n + j];
        inv[r * n + j] -= f * inv[col * n + j];
      }
    }
  }
  return inv;
}

/**
 * The network of ``value``'s wires. ``nodes``: which node each wire is and each element's pins are
 * (the simulation's); ``known``: the elements whose terminals' currents it gives.
 */
export function flowGraph(
  value: SchematicData,
  library: SymbolLibrary,
  nodes: { wires: (string | null)[]; pins: Record<string, (string | null)[]> },
  known: (id: string) => boolean,
): FlowGraph {
  const G = library.grid;
  const index = new Map<string, number>(); // "node|x,y" → point
  const where: Point[] = [];
  const point = (node: string, p: Point) => {
    const key = `${node}|${p[0]},${p[1]}`;
    let i = index.get(key);
    if (i === undefined) {
      index.set(key, (i = where.length));
      where.push(p);
    }
    return i;
  };
  // where wires meet: their ends (a T-junction too: an end on another wire's middle)
  const meets = new Map<string, Point[]>();
  value.wires.forEach((w, i) => {
    const node = nodes.wires[i];
    if (!node || w.points.length < 2) return;
    const at = meets.get(node) ?? [];
    at.push(w.points[0] as Point, w.points[w.points.length - 1] as Point);
    meets.set(node, at);
  });
  const segments: Segment[] = [];
  const ends: [number, number][] = [];
  value.wires.forEach((w, i) => {
    const node = nodes.wires[i];
    if (!node) return;
    const at = meets.get(node) ?? [];
    for (let k = 1; k < w.points.length; k++) {
      const a = w.points[k - 1] as Point,
        b = w.points[k] as Point;
      const along = (p: Point) => Math.abs(p[0] - a[0]) + Math.abs(p[1] - a[1]);
      const stops = [a, ...at.filter((p) => onSegment(p, a, b)).sort((p, q) => along(p) - along(q)), b];
      for (let s = 1; s < stops.length; s++) {
        const [p, q] = [stops[s - 1], stops[s]];
        if (p[0] === q[0] && p[1] === q[1]) continue;
        segments.push({ a: [p[0] * G, p[1] * G], b: [q[0] * G, q[1] * G] });
        ends.push([point(node, p), point(node, q)]);
      }
    }
  });
  const count = where.length;
  // the pins on the network: each a current in, or a point held (it takes what is left)
  const held = new Set<number>();
  const inputs: FlowGraph["inputs"] = [];
  const byPlace = new Map<string, number[]>(); // "x,y" → points there (any node)
  index.forEach((i, key) => {
    const place = key.slice(key.indexOf("|") + 1);
    byPlace.set(place, [...(byPlace.get(place) ?? []), i]);
  });
  for (const e of value.elements) {
    const own = nodes.pins[e.id];
    pins(e, library).forEach((p, k) => {
      const node = own?.[k];
      const at = node ? index.get(`${node}|${p[0]},${p[1]}`) : undefined;
      if (at !== undefined && known(e.id)) inputs.push({ id: e.id, pin: k, at });
      else if (at !== undefined) held.add(at);
      else if (!own) for (const i of byPlace.get(`${p[0]},${p[1]}`) ?? []) held.add(i); // a ground, a label
    });
  }
  // the connected pieces, each with at least one point held
  const parent = Array.from({ length: count }, (_, i) => i);
  const find = (i: number): number => (parent[i] === i ? i : (parent[i] = find(parent[i])));
  for (const [a, b] of ends) parent[find(a)] = find(b);
  const pieces = new Map<number, number[]>();
  for (let i = 0; i < count; i++) pieces.set(find(i), [...(pieces.get(find(i)) ?? []), i]);
  const groups: FlowGraph["groups"] = [];
  for (const members of pieces.values()) {
    if (!members.some((i) => held.has(i))) held.add(members[0]);
    const free = members.filter((i) => !held.has(i));
    if (!free.length) continue;
    const at = new Map(free.map((i, k) => [i, k]));
    const n = free.length;
    const L = new Float64Array(n * n); // the free points' Laplacian, every segment a unit conductance
    for (const [a, b] of ends) {
      const [ka, kb] = [at.get(a), at.get(b)];
      if (ka !== undefined) L[ka * n + ka] += 1;
      if (kb !== undefined) L[kb * n + kb] += 1;
      if (ka !== undefined && kb !== undefined) {
        L[ka * n + kb] -= 1;
        L[kb * n + ka] -= 1;
      }
    }
    const inverse = invert(L, n);
    if (inverse) groups.push({ free, inverse });
  }
  return { segments, ends, inputs, groups, count };
}

/** Each segment's current, from its ``a`` towards its ``b`` (A), given the elements' terminals' currents. */
export function segmentCurrents(g: FlowGraph, currents: Record<string, number[]>): Float64Array {
  const inflow = new Float64Array(g.count); // into the network at each point: what the pin puts out
  for (const { id, pin, at } of g.inputs) inflow[at] -= currents[id]?.[pin] ?? 0;
  const potential = new Float64Array(g.count);
  for (const { free, inverse } of g.groups) {
    const n = free.length;
    for (let r = 0; r < n; r++) {
      let s = 0;
      for (let c = 0; c < n; c++) s += inverse[r * n + c] * inflow[free[c]];
      potential[free[r]] = s;
    }
  }
  return Float64Array.from(g.ends, ([a, b]) => potential[a] - potential[b]);
}
