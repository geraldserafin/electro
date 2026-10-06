// A circuit as electro code, written by the page: the series and parallel it is made of (found by the
// classic reduction — two elements between the same two points are one in parallel, a point where exactly
// two meet and nothing is named joins them in series), written with `>>`, `|` and `~` (a loop closed); a
// circuit that is not made of them (a bridge, an op-amp) each element on its points, side by side (`@`). The shape also lays a circuit out
// (`layout.ts`). Python only runs code; it never writes it.

import type { SchematicData, SymbolLibrary } from "@/shared/model/types";
import type { Shape, ShapePart } from "./layout";
import { GROUND, type Quantity } from "./netlist";
import { type NetlistElement, problemOf } from "./problem";

const SOURCES = new Set(["voltage_source", "current_source", "sine_source", "square_source"]);
/** Kinds the same either way round (only their arrows' signs change). */
const SYMMETRIC = new Set(["resistor", "capacitor", "inductor"]);
/** The names a drawing gives points it does not name. */
const AUTO = /^(.+_)?n\d+$/;

type Tree =
  | { leaf: number; id: string; kind: string; flipped: boolean }
  | { named: string }
  | { series: Tree[] }
  | { parallel: Tree[] };
type Edge = [Tree, string, string];

function reversed(t: Tree): Tree {
  if ("leaf" in t) return { ...t, flipped: !t.flipped };
  if ("series" in t) return { series: t.series.map(reversed).reverse() };
  if ("parallel" in t) return { parallel: t.parallel.map(reversed) };
  return t;
}

function leaves(t: Tree): Extract<Tree, { leaf: number }>[] {
  if ("leaf" in t) return [t];
  if ("named" in t) return [];
  return ("series" in t ? t.series : t.parallel).flatMap(leaves);
}

const seriesOf = (...parts: Tree[]): Tree => ({ series: parts.flatMap((p) => ("series" in p ? p.series : [p])) });

function parallelOf(...parts: Tree[]): Tree {
  const first = (p: Tree) => Math.min(...leaves(p).map((l) => l.leaf));
  const flat = parts.flatMap((p) => ("parallel" in p ? p.parallel : [p]));
  return { parallel: flat.sort((a, b) => first(a) - first(b)) };
}

/** Two between the same two (distinct) points, joined. */
function parallelStep(edges: Edge[]): boolean {
  const seen = new Map<string, number>();
  for (const [i, [t, u, v]] of edges.entries()) {
    if (u === v) continue;
    const pair = JSON.stringify([u, v].sort());
    const j = seen.get(pair);
    if (j !== undefined) {
      const [f, a, b] = edges[j];
      edges[j] = [parallelOf(f, u === a && v === b ? t : reversed(t)), a, b];
      edges.splice(i, 1);
      return true;
    }
    seen.set(pair, i);
  }
  return false;
}

/** The two elements at a point where exactly two ends meet, joined (the smallest first, ground last). */
function seriesStep(edges: Edge[], named: Set<string>): boolean {
  const degree = new Map<string, number[]>();
  for (const [i, [, u, v]] of edges.entries()) for (const n of [u, v]) degree.set(n, [...(degree.get(n) ?? []), i]);
  const size = (inc: number[]) => inc.reduce((s, i) => s + leaves(edges[i][0]).length, 0);
  const candidates = [...degree].filter(([, inc]) => inc.length === 2 && inc[0] !== inc[1]);
  candidates.sort(([n, a], [m, b]) => Number(n === GROUND) - Number(m === GROUND) || size(a) - size(b));
  if (!candidates.length) return false;
  const [n, [i, j]] = candidates[0];
  const [[e1, a1, b1], [e2, a2, b2]] = [edges[i], edges[j]];
  const [first, x] = b1 === n ? [e1, a1] : [reversed(e1), b1];
  const [second, y] = a2 === n ? [e2, b2] : [reversed(e2), a2];
  edges.splice(j, 1);
  edges.splice(i, 1);
  edges.push([seriesOf(first, ...(named.has(n) ? [{ named: n }] : []), second), x, y]);
  return true;
}

/** How many direction-sensitive elements a reading direction turns round. */
const against = (t: Tree) => leaves(t).filter((l) => l.flipped && !SYMMETRIC.has(l.kind)).length;

function structure(elements: NetlistElement[]): { loop: Tree[] } | { between: Tree; a: string; b: string } | null {
  if (elements.some((e) => e.nodes.length !== 2)) return null;
  const named = new Set(elements.flatMap((e) => e.nodes).filter((n) => n !== GROUND && !AUTO.test(n)));
  const edges: Edge[] = elements.map(
    (e, k) => [{ leaf: k, id: e.id, kind: e.kind, flipped: false }, ...e.nodes] as Edge,
  );
  while (parallelStep(edges) || seriesStep(edges, named));
  if (edges.length !== 1) return null;
  let [tree, u, v] = edges[0];
  const hasSource = (t: Tree) => leaves(t).some((l) => SOURCES.has(l.kind));
  if ("parallel" in tree) {
    const withSource = tree.parallel.filter(hasSource);
    if (withSource.length > 1) return { between: tree, a: u, b: v };
    const first = withSource[0] ?? tree.parallel[0];
    const rest = tree.parallel.filter((p) => p !== first);
    const load = rest.length === 1 ? rest[0] : parallelOf(...rest);
    const end = (n: string): Tree[] => (named.has(n) ? [{ named: n }] : []);
    [tree, v] = [seriesOf(...end(u), first, ...end(v), reversed(load)), u];
  }
  if (u !== v) return { between: tree, a: u, b: v };
  if (against(reversed(tree)) < against(tree)) tree = reversed(tree);
  const parts = "series" in tree ? tree.series : [tree];
  const start = Math.max(
    0,
    parts.findIndex((p) => "leaf" in p && SOURCES.has(p.kind)),
  );
  return { loop: [...parts.slice(start), ...parts.slice(0, start)] };
}

function part(t: Tree): ShapePart {
  if ("leaf" in t) return { element: t.id, flip: t.flipped && !SYMMETRIC.has(t.kind) };
  if ("named" in t) return { node: t.named };
  if ("series" in t) return { series: t.series.map(part) };
  return { parallel: t.parallel.map(part) };
}

/** The series and parallel a circuit is made of, for the layout; null when it is not made of them. */
export function shapeOf(elements: NetlistElement[]): Shape | null {
  const s = structure(elements);
  if (!s) return null;
  return "loop" in s ? { loop: s.loop.map(part) } : { between: part(s.between), a: s.a, b: s.b };
}

// ------------------------------------------------------------------ the code

const CONSTRUCTORS: Record<string, string> = {
  and_gate: "AND",
  nand_gate: "NAND",
  or_gate: "OR",
  nor_gate: "NOR",
  xor_gate: "XOR",
  not_gate: "NOT",
  dff: "DFlipFlop",
  jkff: "JKFlipFlop",
  opamp: "OpAmp",
  opamp_model: "OpAmpModel",
  rgb_led: "RGBLED",
  lcd1602_i2c: "LCD1602I2C",
};
/** Kinds electro names in capitals: `npn` → `NPN`. */
const CAPITALS = /^(led|npn|pnp|nmos|pmos|vcvs|vccs|ccvs|cccs|ds1307|ili9341|lcd1602|ssd1306)$/;
const KEYWORDS = new Set(
  "False None True and as assert async await break class continue def del elif else except finally for from global if import in is lambda nonlocal not or pass raise return try while with yield".split(
    " ",
  ),
);
const QUANTITIES = { I: "I", U: "U", P: "P", value: "Parameter" } as const;
/** A meter's value is its reading: the current through it, the voltage across it. */
const READS: Record<string, string> = { ammeter: "I", voltmeter: "U" };

const pythonClass = (kind: string) =>
  CONSTRUCTORS[kind] ??
  (CAPITALS.test(kind) ? kind.toUpperCase() : kind.replace(/(^|_)(\w)/g, (_, __, c: string) => c.toUpperCase()));

/** A schematic's name as the Python variable cells see it: `"Układ 1"` → `układ1` (as the kernel's
 *  ``variable``). */
export function variable(name: string): string {
  const v = name.toLowerCase().replace(/[^\p{L}\p{N}_]/gu, "");
  if (!v) return "uklad";
  return /^\p{N}/u.test(v) ? `_${v}` : v;
}

/** A name as a Python identifier: anything else in it dropped, so no name can write code of its own. */
function identifier(name: string): string {
  const v = name.replace(/[^\p{L}\p{N}_]/gu, "_");
  return /^\p{N}/u.test(v) || KEYWORDS.has(v) || !v ? `_${v}` : v;
}

const point = (n: string) => (n === GROUND ? "GND" : `node_${identifier(n)}`);

function value(text: string): string {
  return /^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$/.test(text) ? text : JSON.stringify(text);
}

function quantity(q: Quantity, of: (id: string) => string): string {
  switch (q[0]) {
    case "V":
      return `V(${point(q[1])})`;
    case "U_between":
      return `U(${point(q[1])}, ${point(q[2])})`;
    case "sum":
      return q[1].map(([k, t]) => `${k} * ${quantity(t, of)}`).join(" + ");
    default:
      return `${QUANTITIES[q[0]]}(${of(q[1])})`;
  }
}

function tree(t: ShapePart, of: (id: string) => string, top = false): string {
  if ("element" in t) return t.flip ? `-${of(t.element)}` : of(t.element);
  if ("node" in t) return point(t.node);
  if ("series" in t) {
    const text = t.series.map((p) => tree(p, of)).join(" >> ");
    return top ? text : `(${text})`;
  }
  return `(${t.parallel.map((p) => tree(p, of)).join(" | ")})`;
}

function pointsIn(s: Shape): Set<string> {
  const used = new Set("between" in s ? [s.a, s.b] : []);
  const visit = (t: ShapePart) => {
    if ("node" in t) used.add(t.node);
    else if ("series" in t) t.series.forEach(visit);
    else if ("parallel" in t) t.parallel.forEach(visit);
  };
  ("loop" in s ? s.loop : [s.between]).forEach(visit);
  return used;
}

/** An element with each end on its point: `(a >> R >> b)`, or `(T >> (b @ c @ e))`. */
const placed = (name: string, points: string[]) =>
  points.length === 2 ? `(${points[0]} >> ${name} >> ${points[1]})` : `(${name} >> (${points.join(" @ ")}))`;

/** What is given of an element, as code: its value (a meter's its reading), its other parameters, its part. */
function givenOf(e: NetlistElement, name: string): string[] {
  const v = e.value?.trim();
  const main = v && v !== "?" ? v : null;
  const params = Object.entries(e.params ?? {});
  if (main && READS[e.kind]) return [`${READS[e.kind]}(${name}): ${value(main)}`];
  if (e.part && !params.length && !main) return [`${name}: part(${JSON.stringify(e.part)})`];
  if (!params.length) return main ? [`${name}: ${value(main)}`] : [];
  const all = [...(main ? [["", main]] : []), ...params.map(([w, x]) => [w, String(x)])];
  return [`${name}: {${all.map(([w, x]) => `${JSON.stringify(w)}: ${value(x)}`).join(", ")}}`];
}

/** A problem (its elements and what its marks give) as electro code, assigned to `name`'s variable. */
export function codeOf(problem: { elements: NetlistElement[]; given: [Quantity, string][] }, name: string): string {
  const { elements, given } = problem;
  const names = new Map<string, string>();
  const taken = new Set<string>();
  for (const e of elements) {
    let v = identifier(e.id);
    while (taken.has(v)) v += "_";
    taken.add(v);
    names.set(e.id, v);
  }
  const of = (id: string) => names.get(id) ?? identifier(id);
  const shape = shapeOf(elements);
  const lines = elements.map((e) => `${of(e.id)} = ${pythonClass(e.kind)}(${JSON.stringify(e.id)})`);
  const all = shape ? pointsIn(shape) : new Set(elements.flatMap((e) => e.nodes));
  const points = [...all].filter((n) => n !== GROUND).sort();
  lines.push(...points.map((n) => `${point(n)} = Node(${JSON.stringify(n)})`));
  const circuit = !shape
    ? `(\n    ${elements.map((e) => placed(of(e.id), e.nodes.map(point))).join("\n    @ ")}\n)`
    : "loop" in shape
      ? `~(${shape.loop.map((p) => tree(p, of, true)).join(" >> ")})`
      : `${point(shape.a)} >> ${tree(shape.between, of)} >> ${point(shape.b)}`;
  const data = [
    ...elements.flatMap((e) => givenOf(e, of(e.id))),
    ...given.map(([q, v]) => `${quantity(q, of)}: ${value(v)}`),
  ].join(", ");
  lines.push(`${variable(name)} = Problem(${circuit}${data ? `, {${data}}` : ""})`);
  return lines.join("\n");
}

/** A drawing's code: what it shows as a problem, written as electro code. */
export const writeCode = (sch: SchematicData, lib: SymbolLibrary, name: string) => codeOf(problemOf(sch, lib), name);
