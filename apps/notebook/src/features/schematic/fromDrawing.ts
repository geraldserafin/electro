// A circuit an AI described as data *and* as drawn — each element's terminals where the picture has them
// (`at`: grid units, x right, y down, in the kind's terminal order) and the wires as polylines — drawn so:
// a two-terminal element in the middle between its terminals (on a row or a column, at least 4 apart),
// wires from its pins out to them; one of more terminals by its first. Anything touching connects (a
// wire's end or a pin on another wire's middle, too); wires only crossing do not. Ground (node `0`/`GND`)
// gets its symbol under its lowest point. Its wires joining other than its nodes say, they are laid anew
// (`rerouted`), the elements where they are — or, `strict`, that is said (`mismatch`), for whoever drew it
// to mend. Data only, never code.

import { parseAnswer } from "@/features/notebook/cells/task";
import { si } from "@/features/simulation/format";
import type { Failure } from "@/shared/model/issues";
import type { ElementData, Point, SchematicData, SymbolLibrary } from "@/shared/model/types";
import { isComponent, isMark, key, onSegment, pins } from "./model";
import { connected, GROUND, netlist } from "./netlist";

/** A circuit as data: its elements (kind as the schematic names them), each with its nodes in its
 *  terminals' order (`0`: ground). */
export type Netlist = {
  elements: {
    id: string;
    kind: string;
    value?: string | null;
    text?: string | null;
    nodes: string[];
    at?: [number, number][]; // a drawing's: where its terminals are (grid units), in the nodes' order
  }[];
  wires?: [number, number][][]; // a drawing's: its wires, as polylines
};

type Described = Netlist["elements"][number] & {
  of?: string | null;
  between?: [number, number][] | null;
  flip?: boolean | null;
};

export type Drawn =
  | { schematic: SchematicData; rerouted: boolean }
  | { error: Failure & { mismatch?: string[]; dangling?: string[] } };

const STEP: Record<string, number> = { "1,0": 0, "0,1": 90, "-1,0": 180, "0,-1": 270 };
const NAME = /^[\p{L}_][\p{L}\p{N}_]*$/u;

const sign = (x: number) => (x > 0 ? 1 : 0) - (x < 0 ? 1 : 0);
const point = (p: number[]): Point => [Math.round(Number(p[0])), Math.round(Number(p[1]))];
const groundName = (n: string) => (n === "0" ? GROUND : n);

/** From `a` to `b` along the grid (one corner when they share no row or column). */
const path = (a: Point, b: Point): Point[] => (a[0] === b[0] || a[1] === b[1] ? [a, b] : [a, [b[0], a[1]], b]);

class Said extends Error {
  constructor(readonly failure: Failure & { mismatch?: string[]; dangling?: string[] }) {
    super(failure.data);
  }
}

const said = (issue: Failure["issue"] & object, data = issue.type) => new Said({ data, issue });

/** A wire as a model may write it: `[[x, y], …]`, or `"[x, y], [x, y]"`, or `[x, y, x, y, …]`. */
function polyline(w: unknown): number[][] {
  let points = typeof w === "string" ? (JSON.parse(`[${w}]`) as unknown[]) : (w as unknown[]);
  if (!Array.isArray(points)) return [];
  if (points.length && points.every((v) => typeof v === "number")) {
    const flat = points as number[];
    points = flat.flatMap((_, i) => (i % 2 === 0 && i + 1 < flat.length ? [[flat[i], flat[i + 1]]] : []));
  }
  return points.filter((p): p is number[] => Array.isArray(p) && p.length === 2);
}

/** A number as one would write it on a drawing: `2200` → `2.2k`; anything else (a symbol, a phasor) as it is. */
export function readable(value: string): string {
  const n = parseAnswer(value);
  if (n === null || !Number.isFinite(n)) return value;
  const short = si(n, "").replace(" ", "");
  const back = parseAnswer(short);
  return back !== null && Math.abs(back - n) <= 1e-12 * Math.abs(n) ? short : value;
}

const drawnValue = (v: unknown) => (v === null || v === undefined || v === "" ? null : readable(String(v)));

/** Drawn too small (a resistor 2 units long), or side by side closer than 6: how much bigger. */
function scaleOf(elements: Described[]): number {
  const two = elements.filter((e) => e.at?.length === 2).map((e) => e.at!.map((p) => p.map(Number)));
  const spans = two.map(([a, b]) => Math.max(Math.abs(a[0] - b[0]), Math.abs(a[1] - b[1]))).filter((s) => s > 0);
  let scale = spans.length ? Math.max(1, Math.ceil(4 / Math.min(...spans))) : 1;
  const lines = [0, 1].map((axis) =>
    [...new Set(two.filter(([a, b]) => a[axis] === b[axis]).map(([a]) => a[axis]))].sort((x, y) => x - y),
  );
  const gaps = lines.flatMap((line) => line.slice(1).map((b, i) => b - line[i])).filter((g) => g > 0);
  if (gaps.length) scale = Math.max(scale, Math.ceil(6 / Math.min(...gaps)));
  return scale;
}

/** An arrow along its longer side from its tail; a voltage's as long as drawn; a loop's current at a point. */
function arrow(e: Described): ElementData {
  const base = { id: String(e.id), kind: e.kind, value: drawnValue(e.value), text: String(e.text ?? "") };
  if (e.kind === "mesh_current") return { ...base, at: point(e.at![0]), rotation: 0, flip: e.flip ? true : null };
  const [[x1, y1], [x2, y2]] = e.at!.slice(0, 2).map(point);
  const [dx, dy] = [x2 - x1, y2 - y1];
  const d = Math.abs(dx) >= Math.abs(dy) ? [sign(dx), 0] : [0, sign(dy)];
  if (!d[0] && !d[1]) throw new Said({ data: `${e.id}: its tail and head on one point` });
  return {
    ...base,
    at: [x1, y1],
    rotation: STEP[d.join(",")],
    of: e.of ? String(e.of) : null,
    span: e.kind === "voltage_arrow" ? Math.max(Math.abs(dx), Math.abs(dy)) : null,
    between: e.between ? e.between.slice(0, 2).map(point) : null,
  };
}

/** A component placed as drawn: two terminals in the middle between them, more by the first. */
function placed(e: Described, lib: SymbolLibrary): ElementData {
  const at = (e.at ?? []).map(point);
  const offsets = pins({ id: e.id, kind: e.kind, at: [0, 0], rotation: 0, value: null, text: null }, lib);
  if (e.nodes.length !== offsets.length)
    throw said({ type: "WrongNodeCount", part: e.id, terminals: offsets.length, nodes: e.nodes.map(String) });
  if (at.length !== offsets.length)
    throw new Said({ data: `${e.id}: ${offsets.length} terminal points, not ${at.length}` });
  const base = { id: e.id, kind: e.kind, value: drawnValue(e.value), text: e.text ? String(e.text) : null };
  if (offsets.length !== 2) return { ...base, at: [at[0][0] - offsets[0][0], at[0][1] - offsets[0][1]], rotation: 0 };
  let [[x1, y1], [x2, y2]] = at;
  if (x1 !== x2 && y1 !== y2) {
    if (Math.abs(x2 - x1) >= Math.abs(y2 - y1)) y2 = y1;
    else x2 = x1;
  }
  const length = Math.abs(x2 - x1) + Math.abs(y2 - y1);
  if (length < 4) throw new Said({ data: `${e.id}: its terminals ${JSON.stringify(at)} less than 4 apart` });
  const d = [sign(x2 - x1), sign(y2 - y1)];
  const gap = Math.floor((length - 4) / 2);
  return { ...base, at: [x1 + d[0] * gap, y1 + d[1] * gap], rotation: STEP[d.join(",")] };
}

/** Wires split where a pin or another wire's end is on their middle: touching, so joined. */
function splitAtTouches(wires: Point[][], touching: Point[]): Point[][] {
  const out: Point[][] = [];
  for (const w of wires) {
    let cur: Point[] = [w[0]];
    w.slice(1).forEach((b, i) => {
      const a = w[i];
      const inner = touching
        .filter((p) => onSegment(p, a, b))
        .sort((p, q) => Math.abs(p[0] - a[0]) + Math.abs(p[1] - a[1]) - Math.abs(q[0] - a[0]) - Math.abs(q[1] - a[1]));
      for (const p of inner) {
        cur.push(p);
        out.push(cur);
        cur = [p];
      }
      cur.push(b);
    });
    out.push(cur);
  }
  return out;
}

/** Each node's pins joined, the nearest first, along the grid (ends only on pins: nothing else joined). */
function routes(terminals: Terminal[]): Point[][] {
  const byNode = new Map<string, Point[]>();
  for (const t of terminals) byNode.set(t.node, [...(byNode.get(t.node) ?? []), t.at]);
  const out: Point[][] = [];
  for (const all of byNode.values()) {
    const rest = [...new Map(all.map((p) => [key(p), p])).values()];
    const joined = [rest.shift()!];
    while (rest.length) {
      let best: [Point, number] = [joined[0], 0];
      let shortest = Infinity;
      for (const a of joined)
        rest.forEach((b, i) => {
          const d = Math.abs(a[0] - b[0]) + Math.abs(a[1] - b[1]);
          if (d < shortest) [shortest, best] = [d, [a, i]];
        });
      const [b] = rest.splice(best[1], 1);
      out.push(path(best[0], b));
      joined.push(b);
    }
  }
  return out;
}

interface Terminal {
  id: string;
  index: number;
  node: string;
  at: Point;
}

/** Where the drawing with these wires joins other than its nodes say. */
function mismatchOf(sch: SchematicData, terminals: Terminal[], lib: SymbolLibrary): string[] {
  const point = connected(sch, lib);
  const drawn = new Map<string, Set<string>>();
  const said = new Map<string, Set<string>>();
  for (const t of terminals) {
    const p = point.get(key(t.at))!;
    drawn.set(t.node, (drawn.get(t.node) ?? new Set()).add(p));
    said.set(p, (said.get(p) ?? new Set()).add(t.node));
  }
  return [
    ...[...drawn].filter(([, ps]) => ps.size > 1).map(([n, ps]) => `node ${n} is drawn as ${ps.size} separate pieces`),
    ...[...said.values()]
      .filter((ns) => ns.size > 1)
      .map((ns) => `nodes ${[...ns].sort().join(", ")} are drawn joined`),
  ];
}

export function fromDrawing(data: Netlist, lib: SymbolLibrary, strict = false): Drawn {
  try {
    return drawn(data, lib, strict);
  } catch (error) {
    if (error instanceof Said) return { error: error.failure };
    return { error: { data: String(error) } };
  }
}

function drawn(data: Netlist, lib: SymbolLibrary, strict: boolean): Drawn {
  const all = data.elements as Described[];
  for (const e of all) if (!NAME.test(String(e.id))) throw said({ type: "BadName", name: String(e.id) });
  const marks = all.filter((e) => isMark(e.kind));
  const parts = all.filter((e) => !isMark(e.kind));
  const scale = scaleOf(parts);
  const scaled = (ps?: number[][] | null) =>
    ps?.map((p) => [Number(p[0]) * scale, Number(p[1]) * scale]) as [number, number][];
  const grown = (e: Described): Described => ({
    ...e,
    at: scaled(e.at),
    between: e.between ? scaled(e.between) : null,
  });
  const elements: ElementData[] = marks.map((e) => arrow(scale > 1 ? grown(e) : e));
  const wires: Point[][] = [];
  const terminals: Terminal[] = [];
  for (const raw of parts) {
    const e = scale > 1 ? grown(raw) : raw;
    const nodes = (e.nodes ?? []).map((n) => groundName(String(n)));
    if (e.kind === "terminal") {
      const there = point(e.at![0]);
      elements.push({ id: String(e.id), kind: "terminal", at: there, rotation: 0, value: null, text: null });
      terminals.push({ id: e.id, index: 0, node: nodes[0], at: there });
      continue;
    }
    if (!lib.kinds[e.kind] || !isComponent(e.kind))
      throw said({ type: "UnknownKind", kind: e.kind, available: Object.keys(lib.kinds).filter(isComponent).sort() });
    const element = placed({ ...e, nodes }, lib);
    elements.push(element);
    pins(element, lib).forEach((pin, i) => {
      const there = point(e.at![i]);
      if (key(pin) !== key(there)) wires.push(path(pin, there));
      terminals.push({ id: e.id, index: i, node: nodes[i], at: pin });
    });
  }
  for (const w of data.wires ?? []) {
    const pts = polyline(scale > 1 ? scaled(polyline(w)) : w).map(point);
    if (pts.length >= 2) wires.push([pts[0], ...pts.slice(1).flatMap((b, i) => path(pts[i], b).slice(1))]);
  }
  const touching = [...terminals.map((t) => t.at), ...wires.flatMap((w) => [w[0], w[w.length - 1]])];
  const split = splitAtTouches(wires, touching);
  const grounded = terminals.filter((t) => t.node === GROUND).map((t) => t.at);
  if (grounded.length) {
    const low = grounded.reduce((a, b) => (b[1] > a[1] || (b[1] === a[1] && b[0] < a[0]) ? b : a));
    elements.push({ id: "GND1", kind: "ground", at: low, rotation: 0, value: null, text: null });
  }
  const count = new Map<string, number>();
  for (const t of terminals) count.set(t.node, (count.get(t.node) ?? 0) + 1);
  const alone = terminals
    .filter((t) => count.get(t.node) === 1)
    .map((t) => `${t.id}'s terminal ${t.index + 1} (node ${t.node}) is joined to nothing`);
  if (alone.length) throw new Said({ data: alone.join("; "), dangling: alone });
  const drawing = (lines: Point[][]): SchematicData => ({
    elements,
    wires: lines.filter((w) => new Set(w.map(key)).size > 1).map((points) => ({ points })),
  });
  let sch = drawing(split);
  let mismatch = mismatchOf(sch, terminals, lib);
  let rerouted = false;
  if (mismatch.length && !strict) {
    sch = drawing(routes(terminals));
    mismatch = mismatchOf(sch, terminals, lib);
    rerouted = true;
  }
  if (mismatch.length) throw new Said({ data: mismatch.join("; "), mismatch });
  return { schematic: sch, rerouted };
}

/** A drawing as data, the way `fromDrawing` takes it (ground `0`): for an AI to read a note's circuits. */
export function netlistOf(sch: SchematicData, lib: SymbolLibrary): Netlist {
  const elements = netlist(sch, lib).elements.map(({ id, kind, value, text, nodes }) => ({
    id,
    kind,
    value,
    text,
    nodes: nodes.map((n) => (n === GROUND ? "0" : n)),
  }));
  return { elements };
}
