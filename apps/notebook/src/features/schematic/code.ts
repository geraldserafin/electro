// A circuit as electro code, written by the page: the series and parallel it is made of (found by the
// classic reduction — two elements between the same two points are one in parallel, a point where exactly
// two meet and nothing is named joins them in series), written with `>>`, `|` and `~` (a loop closed); what
// is left of a circuit not made of them (a bridge) as walks from point to point (`a >> R_1 >> b >> R_2 >> c`),
// an element of more ends on its points, side by side (`@`). A point or an element is a variable only when the
// code uses it more than once. The shape also lays a circuit out (`layout.ts`). Python only runs code; it
// never writes it.

import type { SchematicData, SymbolLibrary } from "@/shared/model/types";
import type { Shape, ShapePart } from "./layout";
import { GROUND, type Quantity } from "./netlist";
import { type NetlistElement, solveData } from "./problem";

const SOURCES = new Set(["voltage_source", "current_source", "sine_source", "square_source"]);
/** Kinds the same either way round (only their arrows' signs change). */
export const SYMMETRIC = new Set(["resistor", "capacitor", "inductor"]);
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

/** The points a drawing names itself (not ground, not the ones it numbers). */
const namedIn = (elements: NetlistElement[]) =>
  new Set(elements.flatMap((e) => e.nodes).filter((n) => n !== GROUND && !AUTO.test(n)));

/** Its elements as edges between points, every series and parallel joined into one (``keep``: points a
 *  series keeps by name). */
function reduced(elements: NetlistElement[], keep: Set<string>): Edge[] {
  const edges: Edge[] = elements.map(
    (e, k) => [{ leaf: k, id: e.id, kind: e.kind, flipped: false }, ...e.nodes] as Edge,
  );
  while (parallelStep(edges) || seriesStep(edges, keep));
  return edges;
}

const hasSource = (t: Tree) => leaves(t).some((l) => SOURCES.has(l.kind));

function structure(
  elements: NetlistElement[],
  named = namedIn(elements),
): { loop: Tree[]; at: string } | { between: Tree; a: string; b: string } | null {
  if (elements.some((e) => e.nodes.length !== 2)) return null;
  const edges = reduced(elements, named);
  if (edges.length !== 1) return null;
  let [tree, u, v] = edges[0];
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
  return { loop: [...parts.slice(start), ...parts.slice(0, start)], at: u };
}

/** A walk along edges: where it starts, then each edge and the point it reaches. */
type Trail = { start: string; path: [Tree, string][] };

/** The edges as few walks as a greedy walk finds, each from a source where there is one, else from a
 *  point where an odd number meet (a walk must end there). */
function trailsOf(edges: Edge[]): Trail[] {
  const used = new Set<number>();
  const free = (n?: string) =>
    edges.flatMap((e, i) => (!used.has(i) && (n === undefined || e[1] === n || e[2] === n) ? [i] : []));
  const odd = (n: string) => free(n).length % 2 === 1;
  const trails: Trail[] = [];
  while (free().length) {
    const left = free();
    const bySource = left.find((i) => hasSource(edges[i][0]));
    const ends = left.flatMap((i) => [edges[i][1], edges[i][2]]);
    const start = bySource !== undefined ? edges[bySource][1] : (ends.find(odd) ?? ends[0]);
    const trail: Trail = { start, path: [] };
    for (let at = start; free(at).length; ) {
      const here = free(at);
      const i = here.find((j) => hasSource(edges[j][0])) ?? here[0];
      const [t, a, b] = edges[i];
      used.add(i);
      const [step, next] = a === at ? [t, b] : [reversed(t), a];
      trail.path.push([step, next]);
      at = next;
    }
    trails.push(trail);
  }
  return trails;
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
const CAPITALS = /^(led|npn|pnp|nmos|pmos|vcvs|vccs|ccvs|cccs|ds1307|ili9341|lcd1602|mcp4822|ssd1306)$/;
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

/** What may be sought besides a quantity: the resistance between two points, the Thévenin resistance an
 *  element sees. */
export type Sought = Quantity | ["R", string, string] | ["Rth", string];

/** How the code names a point (``pt``) and an element (``of``): a variable when it is used more than once,
 *  else written where it is used. */
type Naming = { pt: (n: string) => string; of: (id: string) => string };

function value(text: string): string {
  return /^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$/.test(text) ? text : JSON.stringify(text);
}

function quantity(q: Sought, { pt, of }: Naming): string {
  switch (q[0]) {
    case "V":
      return `V(${pt(q[1])})`;
    case "U_between":
      return `U(${pt(q[1])}, ${pt(q[2])})`;
    case "R":
      return `Resistance(${pt(q[1])}, ${pt(q[2])})`;
    case "Rth":
      return `Thevenin(${of(q[1])})`;
    case "sum":
      return q[1].map(([k, t]) => `${k} * ${quantity(t, { pt, of })}`).join(" + ");
    default:
      return `${QUANTITIES[q[0]]}(${of(q[1])})`;
  }
}

/** The elements and the points a quantity is of. */
function about(q: Sought): { elements: string[]; points: string[] } {
  switch (q[0]) {
    case "V":
      return { elements: [], points: [q[1]] };
    case "U_between":
    case "R":
      return { elements: [], points: [q[1], q[2]] };
    case "sum": {
      const all = q[1].map(([, t]) => about(t));
      return { elements: all.flatMap((x) => x.elements), points: all.flatMap((x) => x.points) };
    }
    default:
      return { elements: [q[1]], points: [] };
  }
}

function tree(t: ShapePart, naming: Naming, top = false): string {
  if ("element" in t) return t.flip ? `-${naming.of(t.element)}` : naming.of(t.element);
  if ("node" in t) return naming.pt(t.node);
  if ("series" in t) {
    const text = t.series.map((p) => tree(p, naming)).join(" >> ");
    return top ? text : `(${text})`;
  }
  return `(${t.parallel.map((p) => tree(p, naming)).join(" | ")})`;
}

/** A walk as code: ``a >> R_1 >> b >> R_2 >> c``; one back where it began, that point named nowhere else
 *  (``closable``), a loop: ``~(R_1 >> b >> R_2)``. */
function walk({ start, path }: Trail, naming: Naming, closable: (n: string) => boolean): string {
  const steps = path.flatMap(([t, n], k) => [
    tree(part(t), naming, true),
    ...(k < path.length - 1 ? [naming.pt(n)] : []),
  ]);
  const end = path[path.length - 1][1];
  if (end === start && closable(start)) return `~(${steps.join(" >> ")})`;
  return [naming.pt(start), ...steps, naming.pt(end)].join(" >> ");
}

/** An element with each end on its point: `(T >> (b @ c @ e))`. */
const placed = (name: string, points: string[]) => `(${name} >> (${points.join(" @ ")}))`;

/** The circuit as code: one series–parallel piece as such; else its two-ended elements, series and
 *  parallel joined, as walks, and every other element on its points, side by side (``@``). ``keep``: the
 *  points a series keeps by name (named ones, ones something else is on). */
function circuitOf(elements: NetlistElement[], keep: Set<string>, naming: Naming, closable: (n: string) => boolean) {
  const multi = elements.filter((e) => e.nodes.length !== 2);
  const s = multi.length ? null : structure(elements, keep);
  if (s && "between" in s) return `${naming.pt(s.a)} >> ${tree(part(s.between), naming, true)} >> ${naming.pt(s.b)}`;
  // (a loop closed at a point kept by name: written where the loop has it, else the loop is a walk)
  const closed = s && "loop" in s && (!keep.has(s.at) || s.loop.some((p) => "named" in p && p.named === s.at));
  if (s && closed) return `~(${s.loop.map((p) => tree(part(p), naming, true)).join(" >> ")})`;
  const two = elements.filter((e) => e.nodes.length === 2);
  const pieces = [
    ...trailsOf(reduced(two, keep)).map((t) => walk(t, naming, closable)),
    ...multi.map((e) => placed(naming.of(e.id), e.nodes.map(naming.pt))),
  ];
  return pieces.length === 1
    ? pieces[0]
    : `(\n    ${pieces.map((p) => (p.startsWith("(") ? p : `(${p})`)).join("\n    @ ")}\n)`;
}

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

/** Where the circuit's ``final`` call stands in what the code shows after the circuit (``show``, as the
 *  code view read it back: ``steps(__final__)``). */
export const FINAL = "__final__";

/** Names the code's own lines use: no point or element may take one. */
const RESERVED = ["GND", "I", "U", "V", "P", "Node", "Parameter", "Resistance", "Thevenin", "part"];

/** A drawing (its elements, what its marks give, what is sought) as electro code that runs as it is: the
 *  elements and points used more than once as variables, the circuit assigned to ``name``'s variable, and
 *  its ``final`` with the values and what is sought. */
export function codeOf(
  problem: { elements: NetlistElement[]; given: [Quantity, string][]; find?: Sought[] },
  name: string,
  show?: string | null,
): string {
  const { elements, given, find = [] } = problem;
  const asked = [...given.map(([q]) => q), ...find].map(about);
  const keep = new Set([
    ...namedIn(elements),
    ...elements.flatMap((e) => (e.nodes.length !== 2 ? e.nodes : [])),
    ...asked.flatMap((x) => x.points),
  ]);
  // an element is used in the circuit, in the values when something is given of it, in what is asked
  const uses = new Map<string, number>();
  const count = (id: string) => uses.set(id, (uses.get(id) ?? 0) + 1);
  for (const e of elements) [e.id, ...(givenOf(e, "").length ? [e.id] : [])].forEach(count);
  asked.forEach((x) => x.elements.forEach(count));
  const taken = new Set(RESERVED);
  const own = (raw: string) => {
    let v = identifier(raw);
    while (taken.has(v)) v += "_";
    taken.add(v);
    return v;
  };
  const kinds = new Map(elements.map((e) => [e.id, e.kind]));
  const vars = new Map(elements.filter((e) => uses.get(e.id)! > 1).map((e) => [e.id, own(e.id)]));
  const of = (id: string) => vars.get(id) ?? `${pythonClass(kinds.get(id) ?? "")}(${JSON.stringify(id)})`;
  // the points: written once to count them, then each used more than once a variable
  const said = new Map<string, number>();
  const counting: Naming = { pt: (n) => (said.set(n, (said.get(n) ?? 0) + 1), ""), of };
  const write = (naming: Naming, closable: (n: string) => boolean) => ({
    circuit: circuitOf(elements, keep, naming, closable),
    data: [
      ...elements.flatMap((e) => givenOf(e, of(e.id))),
      ...given.map(([q, v]) => `${quantity(q, naming)}: ${value(v)}`),
    ].join(", "),
    find: find.map((q) => quantity(q, naming)).join(", "),
  });
  write(counting, () => false);
  const points = [...said]
    .filter(([n, k]) => n !== GROUND && k > 1)
    .map(([n]) => n)
    .sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
  const pointVars = new Map(points.map((n) => [n, own(n)]));
  const pt = (n: string) =>
    n === GROUND ? "GND" : (pointVars.get(n) ?? (AUTO.test(n) ? "Node()" : `Node(${JSON.stringify(n)})`));
  const code = write({ pt, of }, (n) => said.get(n) === 2);
  const v = variable(name);
  const args = [...(code.data || code.find ? [`{${code.data}}`] : []), ...(code.find ? [`find=[${code.find}]`] : [])];
  return [
    ...elements
      .filter((e) => vars.has(e.id))
      .map((e) => `${vars.get(e.id)} = ${pythonClass(e.kind)}(${JSON.stringify(e.id)})`),
    ...(points.length
      ? [
          `${points.map((n) => pointVars.get(n)).join(", ")} = ${points.map((n) => `Node(${JSON.stringify(n)})`).join(", ")}`,
        ]
      : []),
    `${v} = ${code.circuit}`,
    ...(show ? show.split(FINAL) : ["", ""]).join(`${v}.final(${args.join(", ")})`).split("\n"),
  ].join("\n");
}

/** A drawing's code: its circuit, values and what is sought, written as electro code. */
export const writeCode = (sch: SchematicData, lib: SymbolLibrary, name: string, show?: string | null) => {
  const { elements, given, sought } = solveData(sch, lib);
  return codeOf({ elements, given, find: sought.map(([, q]) => q) }, name, show);
};
