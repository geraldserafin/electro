// A circuit laid out on the grid from the series and parallel it is made of (`code.ts`'s `shapeOf`):
// series goes along the line, parallel stacks branches side by side, a
// loop closes back under itself. Laid out in "flow" coordinates (u along the current, v across it); the
// page's orientation only maps (u, v) to the screen, so one layout gives horizontal and vertical drawings.
// Room is kept for the texts drawn beside each element: its name above (or left of) it, results below.
import type { ElementData, Point, SchematicData, WireData } from "@/shared/model/types";
import { library } from "./library";
import { kindInfo, pins, simplify } from "./model";
import type { NetlistElement } from "./problem";

type Vec = [number, number];
export type ShapePart =
  | { element: string; flip: boolean }
  | { node: string }
  | { series: ShapePart[] }
  | { parallel: ShapePart[] };
export type Shape = { loop: ShapePart[] } | { between: ShapePart; a: string; b: string };

const RIGHT: Vec = [1, 0],
  LEFT: Vec = [-1, 0],
  UP: Vec = [0, -1],
  DOWN: Vec = [0, 1];
const PINS = 4, // an element's pins apart
  STUB = 1, // wire between a parallel bus and the outside
  GAP = 1, // free space between stacked branches
  LINE = 0.8, // a text line's height (grid units)
  CHAR = 0.37, // a glyph's width
  RESULT_CHARS = 14, // room for "I = 12.55 mA ↓"
  MARGIN = 3; // between the drawing and the top-left corner, as the editor keeps it
const AUTO = /^(.+_)?n\d+$/;
const ROTATION: Record<string, number> = { "1,0": 0, "0,1": 90, "-1,0": 180, "0,-1": 270 };
const DRAWN_AS: Record<string, string> = { opamp_model: "opamp" };

class Frame {
  constructor(
    readonly u: Vec,
    readonly v: Vec,
  ) {}
  screen([a, b]: Vec): Vec {
    return [a * this.u[0] + b * this.v[0], a * this.u[1] + b * this.v[1]];
  }
  local([x, y]: Vec): Vec {
    return [x * this.u[0] + y * this.u[1], x * this.v[0] + y * this.v[1]];
  }
  /** A screen box (around an anchor) in local coordinates. */
  box(x0: number, x1: number, y0: number, y1: number): Box {
    const corners = [x0, x1].flatMap((x) => [y0, y1].map((y) => this.local([x, y])));
    return [
      Math.min(...corners.map((c) => c[0])),
      Math.max(...corners.map((c) => c[0])),
      Math.min(...corners.map((c) => c[1])),
      Math.max(...corners.map((c) => c[1])),
    ];
  }
}

type Box = [number, number, number, number];

/** Child local → parent local: a quarter turn or a reflection, and a shift. */
class Transform {
  constructor(
    readonly a = 1,
    readonly b = 0,
    readonly c = 0,
    readonly d = 1,
    readonly du = 0,
    readonly dv = 0,
  ) {}
  point([u, v]: Vec): Vec {
    return [this.a * u + this.b * v + this.du, this.c * u + this.d * v + this.dv];
  }
  vector([u, v]: Vec): Vec {
    return [this.a * u + this.b * v, this.c * u + this.d * v];
  }
}

interface Item {
  kind: "wire" | "element" | "ground" | "label" | "terminal" | "reserve";
  points: Vec[];
  box: Box;
  data?: { id?: string; text?: string };
  axis: Vec; // an element's: from its first pin to its second
}

function moved(item: Item, t: Transform): Item {
  const corners = [item.box[0], item.box[1]].flatMap((u) => [item.box[2], item.box[3]].map((v) => t.vector([u, v])));
  return {
    ...item,
    points: item.points.map((p) => t.point(p)),
    box: [
      Math.min(...corners.map((c) => c[0])),
      Math.max(...corners.map((c) => c[0])),
      Math.min(...corners.map((c) => c[1])),
      Math.max(...corners.map((c) => c[1])),
    ],
    axis: t.vector(item.axis),
  };
}

class Block {
  items: Item[] = [];
  constructor(
    readonly frame: Frame,
    public length = 0,
  ) {}
  wire(...points: Vec[]) {
    for (let i = 1; i < points.length; i++)
      if (points[i - 1][0] !== points[i][0] || points[i - 1][1] !== points[i][1])
        this.items.push({ kind: "wire", points: [points[i - 1], points[i]], box: [0, 0, 0, 0], axis: [1, 0] });
  }
  reserve(p: Vec, [x0, x1, y0, y1]: Box) {
    this.items.push({ kind: "reserve", points: [p], box: this.frame.box(x0, x1, y0, y1), axis: [1, 0] });
  }
  place(child: Block, t: Transform) {
    this.items.push(...child.items.map((i) => moved(i, t)));
  }
  extent(): Box {
    const us = [0, this.length],
      vs = [0];
    for (const i of this.items)
      for (const [u, v] of i.points) {
        us.push(u + i.box[0], u + i.box[1]);
        vs.push(v + i.box[2], v + i.box[3]);
      }
    return [Math.min(...us), Math.max(...us), Math.min(...vs), Math.max(...vs)];
  }
}

/** A text block of ``lines`` lines on ``side`` of an anchor, as a screen box. */
function textBox(side: Vec, width: number, lines: number): Box {
  const h = LINE * lines;
  if (side === DOWN) return [-width / 2, width / 2, 0.2, 0.2 + h];
  if (side === UP) return [-width / 2, width / 2, -0.2 - h, -0.2];
  if (side === RIGHT) return [0.3, 0.3 + width, -h / 2, h / 2];
  return [-0.3 - width, -0.3, -h / 2, h / 2];
}

const textWidth = (text: string) => CHAR * text.replace(/_/g, "").length + 0.2;

export class CannotLayOut extends Error {}

function lay(part: ShapePart, frame: Frame, elements: Map<string, NetlistElement>): Block {
  if ("element" in part) return element(part.element, part.flip, frame, elements);
  if ("node" in part) {
    const block = new Block(frame);
    if (part.node === "GND")
      block.items.push({ kind: "ground", points: [[0, 0]], box: frame.box(-0.6, 0.6, 0, 1), axis: [1, 0] });
    else if (!AUTO.test(part.node))
      block.items.push({
        kind: "label",
        points: [[0, 0]],
        box: frame.box(-0.2, textWidth(part.node) + 0.4, -LINE - 0.4, 0),
        data: { text: part.node },
        axis: [1, 0],
      });
    return block;
  }
  if ("series" in part) {
    const block = new Block(frame);
    for (const p of part.series) {
      const child = lay(p, frame, elements);
      block.place(child, new Transform(1, 0, 0, 1, block.length));
      block.length += child.length;
    }
    return block;
  }
  return parallel(part.parallel, frame, elements, true);
}

function element(id: string, flip: boolean, frame: Frame, elements: Map<string, NetlistElement>): Block {
  const e = elements.get(id);
  if (e?.nodes.length !== 2) throw new CannotLayOut(id);
  const axis: Vec = flip ? [-1, 0] : [1, 0];
  const onScreen = frame.screen(axis);
  const [labelSide, resultSide] = onScreen[1] === 0 ? [UP, DOWN] : [LEFT, RIGHT];
  const label = e.value ? `${id} = ${e.value} ${kindInfo(e.kind)?.unit ?? ""}` : id;
  const probe = new Block(frame);
  probe.reserve([0, 0], textBox(labelSide, textWidth(label) + 1.5, 1));
  probe.reserve([0, 0], textBox(resultSide, CHAR * RESULT_CHARS, 2));
  const [umin, umax] = probe.extent();
  const half = Math.max(PINS / 2, Math.ceil(Math.max(-umin, umax) + 0.2));
  const block = new Block(frame, 2 * half);
  const first = flip ? half + PINS / 2 : half - PINS / 2;
  block.wire([0, 0], [half - PINS / 2, 0]);
  block.wire([half + PINS / 2, 0], [2 * half, 0]);
  block.items.push({ kind: "element", points: [[first, 0]], box: [0, 0, 0, 0], data: { id }, axis });
  block.place(probe, new Transform(1, 0, 0, 1, half));
  return block;
}

function parallel(parts: ShapePart[], frame: Frame, elements: Map<string, NetlistElement>, outer: boolean): Block {
  const children = parts.map((p) => lay(p, frame, elements));
  const inner = Math.max(...children.map((c) => c.length));
  const block = new Block(frame, inner + 2 * STUB);
  const offsets: number[] = [];
  let v = 0;
  children.forEach((child, i) => {
    const [, , vmin, vmax] = child.extent();
    if (i) v += Math.ceil(-vmin) + GAP;
    offsets.push(v);
    v += Math.ceil(vmax);
    block.place(child, new Transform(1, 0, 0, 1, STUB, offsets[i]));
    block.wire([STUB + child.length, offsets[i]], [STUB + inner, offsets[i]]);
  });
  if (outer) {
    block.wire([0, 0], [STUB, 0]);
    block.wire([STUB + inner, 0], [inner + 2 * STUB, 0]);
  }
  for (let i = 1; i < offsets.length; i++) {
    block.wire([STUB, offsets[i - 1]], [STUB, offsets[i]]);
    block.wire([STUB + inner, offsets[i - 1]], [STUB + inner, offsets[i]]);
  }
  return block;
}

function loop(parts: ShapePart[], frame: Frame, elements: Map<string, NetlistElement>): Block {
  const child = lay({ series: parts }, frame, elements);
  const [, , , vmax] = child.extent();
  const back = Math.ceil(vmax) + GAP;
  const block = new Block(frame, child.length);
  block.place(child, new Transform());
  block.wire([child.length, 0], [child.length, back], [0, back], [0, 0]);
  return block;
}

/** The circuit of ``shape`` drawn on the grid, its elements' values and texts from ``elements``
 *  (each element's ``text``: what its parameters say, ``textOf``). */
export function layout(
  shape: Shape,
  elements: NetlistElement[],
  textOf: (e: NetlistElement) => string | null,
): SchematicData {
  const byId = new Map(elements.map((e) => [e.id, e]));
  const branches = "between" in shape && "parallel" in shape.between;
  const frame = branches ? new Frame(UP, RIGHT) : new Frame(RIGHT, DOWN);
  let block: Block;
  if ("loop" in shape) block = loop(shape.loop, frame, byId);
  else if (branches) block = parallel((shape.between as { parallel: ShapePart[] }).parallel, frame, byId, false);
  else {
    block = lay(shape.between, frame, byId);
    const end = (name: string, at: Vec): Item =>
      name === "GND"
        ? { kind: "ground", points: [at], box: [0, 0, 0, 0], axis: [1, 0] }
        : AUTO.test(name)
          ? { kind: "terminal", points: [at], box: [0, 0, 0, 0], axis: [1, 0] }
          : { kind: "label", points: [at], box: [0, 0, 0, 0], data: { text: name }, axis: [1, 0] };
    block.items.push(end(shape.a, [0, 0]), end(shape.b, [block.length, 0]));
  }
  return drawn(block, frame, byId, textOf);
}

function drawn(
  block: Block,
  frame: Frame,
  elements: Map<string, NetlistElement>,
  textOf: (e: NetlistElement) => string | null,
): SchematicData {
  const counters: Record<string, number> = {};
  const id = (prefix: string) => `${prefix}${(counters[prefix] = (counters[prefix] ?? 0) + 1)}`;
  const grid = (p: Vec): Point => {
    const [x, y] = frame.screen(p);
    return [Math.round(x), Math.round(y)];
  };
  const out: ElementData[] = [];
  const wires: WireData[] = [];
  for (const item of block.items) {
    if (item.kind === "wire") wires.push({ points: item.points.map(grid) });
    else if (item.kind === "element") {
      const e = elements.get(item.data!.id!)!;
      const rotation = ROTATION[frame.screen(item.axis).map(Math.round).join(",")];
      out.push({
        id: e.id,
        kind: DRAWN_AS[e.kind] ?? e.kind,
        at: grid(item.points[0]),
        rotation,
        value: e.value ?? null,
        text: textOf(e),
      });
    } else if (item.kind === "ground")
      out.push({ id: id("gnd"), kind: "ground", at: grid(item.points[0]), rotation: 0, value: null, text: null });
    else if (item.kind === "label")
      out.push({
        id: id("lbl"),
        kind: "label",
        at: grid(item.points[0]),
        rotation: 0,
        value: null,
        text: item.data!.text!,
      });
    else if (item.kind === "terminal")
      out.push({ id: id("t"), kind: "terminal", at: grid(item.points[0]), rotation: 0, value: null, text: null });
  }
  return fromMargin({ elements: out, wires: wires.map((w) => ({ points: simplify(w.points) })) });
}

/** Shifted to start ``MARGIN`` squares from the top-left corner, as the editor expects. */
function fromMargin(sch: SchematicData): SchematicData {
  const points = [...sch.elements.flatMap((e) => pins(e, library)), ...sch.wires.flatMap((w) => w.points)];
  const dx = MARGIN - Math.min(...points.map((p) => p[0]));
  const dy = MARGIN - Math.min(...points.map((p) => p[1]));
  return {
    elements: sch.elements.map((e) => ({ ...e, at: [e.at[0] + dx, e.at[1] + dy] })),
    wires: sch.wires.map((w) => ({ points: w.points.map(([x, y]) => [x + dx, y + dy] as Point) })),
  };
}
