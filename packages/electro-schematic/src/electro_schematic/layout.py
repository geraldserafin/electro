"""Auto-layout: a circuit's syntax tree → a Schematic on the grid.

The tree already says how to lay things out: ``+`` goes along the line, ``|`` stacks
branches side by side, ``shunt`` hangs an element off the line. Layout happens in
"flow coordinates" (u along the current, v across it); the page orientation only
decides how (u, v) map to the screen, so the same code gives horizontal and vertical
schematics. Room is reserved for the texts a renderer puts next to each element:
the label above (or left of) it, results below (or right of) it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from electro import circuit as ct
from electro.components import Component
from electro.semantics import compile_circuit
from electro.values import UNKNOWN, fmt, to_text

from .model import Element, Schematic, Wire, kind_of

Vec = tuple[float, float]
RIGHT, LEFT, UP, DOWN = (1, 0), (-1, 0), (0, -1), (0, 1)  # screen directions (y grows down)

SYMBOL = 2  # grid units of the element body between its pins' leads (pins are 4 apart)
PINS = 4
STUB = 1  # wire between a parallel bus and the outside
GAP = 1  # free space between stacked branches
LINE = 0.8  # text line height, in grid units (16 px)
CHAR = 0.37  # average glyph width, in grid units (7.4 px)
RESULT_CHARS = 14  # room for "I = 12.55 mA ↓"


class Unsupported(NotImplementedError):
    pass


def _neg(v: Vec) -> Vec:
    return (-v[0], -v[1])


@dataclass(frozen=True)
class Frame:
    """Where the local u and v axes point on the screen."""

    u: Vec
    v: Vec

    def to_screen(self, d: Vec) -> Vec:
        return (d[0] * self.u[0] + d[1] * self.v[0], d[0] * self.u[1] + d[1] * self.v[1])

    def to_local(self, s: Vec) -> Vec:
        return (s[0] * self.u[0] + s[1] * self.u[1], s[0] * self.v[0] + s[1] * self.v[1])

    def box(self, x0, x1, y0, y1):
        """A screen-space box (relative to an anchor) in local coordinates."""
        corners = [self.to_local((x, y)) for x in (x0, x1) for y in (y0, y1)]
        return (min(c[0] for c in corners), max(c[0] for c in corners),
                min(c[1] for c in corners), max(c[1] for c in corners))


@dataclass(frozen=True)
class Transform:
    """Child local → parent local: a 90° rotation or reflection plus a shift."""

    a: int = 1
    b: int = 0
    c: int = 0
    d: int = 1
    du: float = 0
    dv: float = 0

    def point(self, p: Vec) -> Vec:
        return (self.a * p[0] + self.b * p[1] + self.du, self.c * p[0] + self.d * p[1] + self.dv)

    def vector(self, p: Vec) -> Vec:
        return (self.a * p[0] + self.b * p[1], self.c * p[0] + self.d * p[1])


@dataclass
class Item:
    kind: str  # wire | element | ground | label | terminal | reserve
    points: list[Vec]
    box: tuple = (0, 0, 0, 0)  # local extent around points[0]
    data: dict = field(default_factory=dict)
    axis: Vec = (1, 0)  # for elements: local direction from the first pin to the second

    def moved(self, t: Transform) -> Item:
        corners = [t.vector((u, v)) for u in self.box[:2] for v in self.box[2:]]
        box = (min(c[0] for c in corners), max(c[0] for c in corners),
               min(c[1] for c in corners), max(c[1] for c in corners))
        return Item(self.kind, [t.point(p) for p in self.points], box, self.data, t.vector(self.axis))


class Block:
    def __init__(self, frame: Frame, length: float = 0):
        self.frame = frame
        self.length = length
        self.items: list[Item] = []

    def wire(self, *points: Vec):
        for p, q in zip(points, points[1:]):
            if p != q:
                self.items.append(Item("wire", [p, q]))

    def reserve(self, p: Vec, x0, x1, y0, y1):
        self.items.append(Item("reserve", [p], self.frame.box(x0, x1, y0, y1)))

    def place(self, child: Block, t: Transform):
        self.items += [i.moved(t) for i in child.items]

    def extent(self):
        us, vs = [0.0, self.length], [0.0]
        for i in self.items:
            for q in i.points:
                us += [q[0] + i.box[0], q[0] + i.box[1]]
                vs += [q[1] + i.box[2], q[1] + i.box[3]]
        return min(us), max(us), min(vs), max(vs)


def text_box(side: Vec, width: float, lines: int):
    """Screen box of a text block of ``lines`` lines placed on ``side`` of an anchor."""
    h = LINE * lines
    return {
        DOWN: (-width / 2, width / 2, 0.2, 0.2 + h), UP: (-width / 2, width / 2, -0.2 - h, -0.2),
        RIGHT: (0.3, 0.3 + width, -h / 2, h / 2), LEFT: (-0.3 - width, -0.3, -h / 2, h / 2),
    }[side]


def label_sides(axis_on_screen: Vec) -> tuple[Vec, Vec]:
    """(label side, results side): above/below a horizontal element, left/right of a vertical one."""
    return (UP, DOWN) if axis_on_screen[1] == 0 else (LEFT, RIGHT)


def text_width(text: str) -> float:
    return CHAR * len(text.replace("_", "")) + 0.2


# --------------------------------------------------------------------------- layout

@dataclass
class _Context:
    placed: list  # Placed, in netlist order (= traversal order)
    index: int = 0

    def next(self):
        p = self.placed[self.index]
        self.index += 1
        return p


def _layout(c: ct.Circuit, frame: Frame, ctx: _Context) -> Block:
    if isinstance(c, Component):
        return _component(c, frame, ctx, reversed_=False)
    if isinstance(c, ct.Transpose):
        inner = c.part
        if isinstance(inner, Component):
            return _component(inner, frame, ctx, reversed_=True)
        if isinstance(inner, ct.Spider):
            return _layout(inner, frame, ctx)
        child = _layout(inner, Frame(_neg(frame.u), frame.v), ctx)
        block = Block(frame, child.length)
        block.place(child, Transform(-1, 0, 0, 1, child.length, 0))
        return block
    if isinstance(c, ct.Seq):
        block, offset = Block(frame), 0
        for part in c.parts:
            child = _layout(part, frame, ctx)
            block.place(child, Transform(du=offset))
            offset += child.length
        block.length = offset
        return block
    if isinstance(c, ct.Par):
        return _parallel(c, frame, ctx)
    if isinstance(c, ct.Shunt):
        return _shunt(c, frame, ctx)
    if isinstance(c, ct.Close):
        return _close(c, frame, ctx)
    if isinstance(c, ct.Id) and c.n == 1:
        block = Block(frame, 1)
        block.wire((0, 0), (1, 0))
        return block
    if isinstance(c, ct.Spider) and c.dom + c.cod in (1, 2):
        block = Block(frame)
        if c.name == ct.GROUND:
            block.items.append(Item("ground", [(0, 0)], frame.box(-0.6, 0.6, 0, 1)))
        elif c.name:
            block.items.append(Item("label", [(0, 0)], frame.box(-0.2, text_width(c.name) + 0.4, -LINE - 0.4, 0),
                                    {"text": c.name}))
        elif c.dom + c.cod == 1:
            block.items.append(Item("terminal", [(0, 0)], (-0.3, 0.3, -0.3, 0.3)))
        return block
    raise Unsupported(
        f"Nie umiem jeszcze ułożyć {c!r}. Obsługiwane są: elementy dwuzaciskowe, +, |, shunt, "
        "transpose, close/loop, node, ground, wire. Resztę narysuj na siatce."
    )


def _component(comp: Component, frame: Frame, ctx: _Context, reversed_: bool) -> Block:
    if (comp.dom, comp.cod) != (1, 1):
        raise Unsupported(f"Nie umiem jeszcze ułożyć {comp!r} ({comp.type}) — narysuj go na siatce.")
    placed = ctx.next()
    axis = (-1, 0) if reversed_ else (1, 0)
    label_side, result_side = label_sides(frame.to_screen(axis))
    value = "?" if comp.has_value and comp.value is UNKNOWN else fmt(comp.value, comp.unit) if comp.has_value else ""
    label = f"{placed.label} = {value}" if value else placed.label
    probe = Block(frame)
    probe.reserve((0, 0), *text_box(label_side, text_width(label) + 1.5, 1))  # + room for a solved value
    probe.reserve((0, 0), *text_box(result_side, CHAR * RESULT_CHARS, 2))
    umin, umax, _, _ = probe.extent()
    half = max(PINS / 2, math.ceil(max(-umin, umax) + 0.2))
    block = Block(frame, 2 * half)
    first, second = (half - PINS / 2, half + PINS / 2)[:: -1 if reversed_ else 1]
    block.wire((0, 0), (half - PINS / 2, 0))
    block.wire((half + PINS / 2, 0), (2 * half, 0))
    block.items.append(Item("element", [(first, 0)], (0, 0, 0, 0),
                            {"id": placed.label, "kind": kind_of(comp), "value": to_text(comp.value)
                             if comp.has_value else None}, axis))
    block.place(probe, Transform(du=half))
    return block


def _parallel(c: ct.Par, frame: Frame, ctx: _Context, outer: bool = True) -> Block:
    if (c.dom, c.cod) != (1, 1):
        raise Unsupported(f"Nie umiem jeszcze ułożyć połączenia równoległego typu {c.type}.")
    children = [_layout(p, frame, ctx) for p in c.parts]
    inner = max(ch.length for ch in children)
    block = Block(frame, inner + 2 * STUB)
    offsets, v = [], 0
    for i, ch in enumerate(children):
        _, _, vmin, vmax = ch.extent()
        if i:
            v += math.ceil(-vmin) + GAP
        offsets.append(v)
        v += math.ceil(vmax)
        block.place(ch, Transform(du=STUB, dv=offsets[-1]))
        block.wire((STUB + ch.length, offsets[-1]), (STUB + inner, offsets[-1]))
    last = offsets[-1]
    if outer:
        block.wire((0, 0), (STUB, 0))
        block.wire((STUB + inner, 0), (inner + 2 * STUB, 0))
    block.wire((STUB, 0), (STUB, last))
    block.wire((STUB + inner, 0), (STUB + inner, last))
    return block


def _shunt(c: ct.Shunt, frame: Frame, ctx: _Context) -> Block:
    child_frame = Frame(frame.v, _neg(frame.u))  # the element hangs off the line
    child = _layout(c.part, child_frame, ctx)
    _, _, vmin, vmax = child.extent()
    node = max(1, math.ceil(vmax + 0.4))
    block = Block(frame, node + max(1, math.ceil(-vmin + 0.4)))
    block.place(child, Transform(0, -1, 1, 0, node, 0))
    block.wire((0, 0), (block.length, 0))
    block.items.append(Item("ground", [(node, child.length)], frame.box(-0.6, 0.6, 0, 1)))
    return block


def _close(c: ct.Close, frame: Frame, ctx: _Context) -> Block:
    if c.part.dom != 1:
        raise Unsupported(f"Nie umiem jeszcze ułożyć pętli typu {c.part.type}.")
    child = _layout(c.part, frame, ctx)
    _, _, _, vmax = child.extent()
    back = math.ceil(vmax) + GAP
    block = Block(frame, child.length)
    block.place(child, Transform())
    block.wire((child.length, 0), (child.length, back), (0, back), (0, 0))
    return block


# --------------------------------------------------------------------------- public

def layout(circuit: ct.Circuit, *, orientation: str | None = None) -> Schematic:
    """Place ``circuit`` on the grid. ``orientation``: "horizontal" or "vertical"
    (default: vertical for parallel branches, like on a whiteboard)."""
    if orientation is None:
        orientation = "vertical" if isinstance(circuit, ct.Par) else "horizontal"
    frame = {"horizontal": Frame(RIGHT, DOWN), "vertical": Frame(UP, RIGHT)}[orientation]
    ctx = _Context(list(compile_circuit(circuit).parts.values()))
    if isinstance(circuit, ct.Par):
        block = _parallel(circuit, frame, ctx, outer=False)  # just the branches, like on paper
    else:
        block = _layout(circuit, frame, ctx)
        if circuit.dom:
            block.items.append(Item("terminal", [(0, 0)]))
        if circuit.cod:
            block.items.append(Item("terminal", [(block.length, 0)]))
    return _to_schematic(block, frame)


_ROTATION = {RIGHT: 0, DOWN: 90, LEFT: 180, UP: 270}


def _grid(frame: Frame, p: Vec) -> tuple[int, int]:
    x, y = frame.to_screen(p)
    assert abs(x - round(x)) < 1e-9 and abs(y - round(y)) < 1e-9, (x, y)
    return (round(x), round(y))


def _to_schematic(block: Block, frame: Frame) -> Schematic:
    sch, counters = Schematic(), {}

    def auto_id(prefix):
        counters[prefix] = counters.get(prefix, 0) + 1
        return f"{prefix}{counters[prefix]}"

    for item in block.items:
        if item.kind == "wire":
            sch.wires.append(Wire([_grid(frame, p) for p in item.points]))
        elif item.kind == "element":
            rotation = _ROTATION[tuple(int(c) for c in frame.to_screen(item.axis))]
            sch.elements.append(Element(item.data["id"], item.data["kind"], _grid(frame, item.points[0]),
                                        rotation, item.data["value"]))
        elif item.kind == "ground":
            sch.elements.append(Element(auto_id("gnd"), "ground", _grid(frame, item.points[0])))
        elif item.kind == "label":
            sch.elements.append(Element(auto_id("lbl"), "label", _grid(frame, item.points[0]), text=item.data["text"]))
        elif item.kind == "terminal":
            sch.elements.append(Element(auto_id("t"), "terminal", _grid(frame, item.points[0])))
    return sch
