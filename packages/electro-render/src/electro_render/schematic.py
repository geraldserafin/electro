"""Drawing a Schematic (and optionally a solution on top of it) as SVG.

Positions come from the schematic; this module only decides how things look:
symbols, junction dots, and the texts next to each element (label above or left,
results below or right, current arrows pointing the way the current really flows).
"""

from __future__ import annotations

import re
from collections import Counter
from xml.sax.saxutils import escape

from electro import circuit as ct
from electro.components import OPEN, Ammeter, Hole
from electro.values import UNKNOWN, fmt
from electro_schematic import GRID, KINDS, Schematic, layout
from electro_schematic.layout import label_sides
from electro_schematic.model import on_segment

from .symbols import LETTERS, STYLE, SYMBOLS, UPRIGHT

Vec = tuple[float, float]
RIGHT, LEFT, UP, DOWN = (1, 0), (-1, 0), (0, -1), (0, 1)
ARROWS = {RIGHT: "→", LEFT: "←", UP: "↑", DOWN: "↓"}
LINE = 16  # px per text line
CHAR = 7.4  # px per glyph (estimate)
BODY = 15  # px from the wire to the texts


class Svg(str):
    """An SVG document; shows itself in Jupyter-like notebooks."""

    def _repr_svg_(self) -> str:
        return str(self)

    def save(self, path) -> None:
        with open(path, "w", encoding="utf-8") as f:
            f.write(self)


def schematic(what, solution=None, *, orientation: str | None = None) -> Svg:
    """Draw a ``Schematic`` — or a circuit, laid out automatically — optionally with results."""
    sch = what if isinstance(what, Schematic) else layout(what, orientation=orientation)
    return _draw(sch, solution)


# --------------------------------------------------------------------------- texts

def _neg(v: Vec) -> Vec:
    return (-v[0], -v[1])


def _short(c: ct.Circuit) -> str:
    """Compact description of a filled hole: ``R = 2 Ω``, ``E = 17 V (odwr.)``, ``przerwa``."""
    if c is OPEN:
        return "przerwa"
    if isinstance(c, ct.Transpose):
        return f"{_short(c.part)} (odwr.)"
    if isinstance(c, ct.Seq):
        return ", ".join(_short(p) for p in c.parts)
    if hasattr(c, "prefix"):
        return f"{c.prefix} = {fmt(c.value, c.unit)}"
    return "przewód"


def _label_lines(element, solution) -> list[tuple[str, str]]:
    component = element.component()
    label = element.id
    if isinstance(component, Hole):
        realized = solution.realize(label) if solution is not None else None
        return [(f"{label} = ?", "label")] if realized is None else [(f"{label}: {_short(realized)}", "solved")]
    if not component.has_value:
        return [(label, "label")]
    if component.value is UNKNOWN:
        value = solution[label].value if solution is not None else None
        if value is None:
            return [(f"{label} = ?", "label")]
        return [(f"{label} = {fmt(value, component.unit)}", "solved")]
    return [(f"{label} = {fmt(component.value, component.unit)}", "label")]


def _result_lines(element, solution, flow: Vec) -> list[tuple[str, str]]:
    result = solution[element.id]
    lines, sign = [], 1
    if result.I is not None:
        current = result.I
        if current.is_real and current.is_number:
            sign = -1 if current < 0 else 1  # draw the arrow the way the current really flows
            lines.append((f"I = {fmt(sign * current, 'A')} {ARROWS[flow if sign > 0 else _neg(flow)]}", "result"))
        else:
            lines.append((f"I = {fmt(current, 'A')}", "result"))
    if result.U is not None and not isinstance(element.component(), Ammeter):
        lines.append((f"U = {fmt(sign * result.U, 'V')}", "result"))
    return lines


_SUB = re.compile(r"([A-Za-z]+)_([A-Za-z0-9]+)")


def _tspans(text: str) -> str:
    """``R_1 = 10 Ω`` → R with a lowered 1; text after a subscript is raised back."""
    out, pos, lowered = [], 0, False
    for m in _SUB.finditer(text):
        before = escape(text[pos:m.start()] + m.group(1))
        out.append(f'<tspan dy="-4">{before}</tspan>' if lowered else before)
        out.append(f'<tspan class="sub" dy="4">{escape(m.group(2))}</tspan>')
        lowered, pos = True, m.end()
    rest = escape(text[pos:])
    if rest:
        out.append(f'<tspan dy="-4">{rest}</tspan>' if lowered else rest)
    return "".join(out)


# --------------------------------------------------------------------------- drawing

def _junctions(sch: Schematic) -> list[tuple[int, int]]:
    """Grid points where three or more connected wires/pins meet (same rules as Schematic.nodes)."""
    count: Counter = Counter()
    pins = {p for e in sch.elements if e.kind != "label" for p in e.pins()}
    for e in sch.elements:
        if e.kind != "label":
            for p in e.pins():
                count[p] += 1
    free_ends = set()
    for w in sch.wires:
        for end in (w.points[0], w.points[-1]):
            count[end] += 1
            if end not in pins:
                free_ends.add(end)
    for w in sch.wires:  # a free end on another wire's corner or middle: that wire counts twice
        for p in free_ends:
            if p in w.points[1:-1] or any(on_segment(p, a, b) for a, b in w.segments()):
                count[p] += 2
    return [p for p, n in count.items() if n >= 3]


def _text_box(side: Vec, lines) -> tuple[float, float, float, float]:
    """Box of a text block placed on ``side`` of its anchor, relative to the anchor."""
    w = max(CHAR * len(t.replace("_", "")) + 4 for t, _ in lines)
    h = LINE * len(lines)
    return {
        DOWN: (-w / 2, w / 2, 4, 4 + h), UP: (-w / 2, w / 2, -4 - h, -4),
        RIGHT: (6, 6 + w, -h / 2, h / 2), LEFT: (-6 - w, -6, -h / 2, h / 2),
    }[side]


def _hits(box, segments, boxes=()) -> int:
    """How many segments (wires, element bodies) and texts already placed an absolute box overlaps."""
    x0, x1, y0, y1 = box
    count = 0
    for (ax, ay), (bx, by) in segments:
        if min(ax, bx) <= x1 and max(ax, bx) >= x0 and min(ay, by) <= y1 and max(ay, by) >= y0:
            count += 1
    for bx0, bx1, by0, by1 in boxes:
        if bx0 < x1 and bx1 > x0 and by0 < y1 and by1 > y0:
            count += 2  # text on text is worse than text on a wire
    return count


class _Canvas:
    def __init__(self):
        self.items: list[str] = []
        self.cards: list[str] = []  # drawn under all texts, so no card hides another text
        self.texts: list[str] = []
        self.xs: list[float] = []
        self.ys: list[float] = []

    def grow(self, x, y):
        self.xs.append(x)
        self.ys.append(y)

    def text(self, x, y, side: Vec, lines: list[tuple[str, str]]):
        if not lines:
            return
        x0, x1, y0, y1 = _text_box(side, lines)
        anchor, tx = {DOWN: ("middle", x), UP: ("middle", x), RIGHT: ("start", x + x0), LEFT: ("end", x + x1)}[side]
        # a background-coloured card under the text keeps it readable where a wire runs behind it
        self.cards.append(f'<rect class="halo" x="{x + x0:g}" y="{y + y0 + 1:g}" width="{x1 - x0:g}" '
                          f'height="{y1 - y0 - 1:g}" rx="2"/>')
        for i, (text, cls) in enumerate(lines):
            ty = y + y0 + 12 + i * LINE
            self.texts.append(f'<text class="{cls}" x="{tx:g}" y="{ty:g}" text-anchor="{anchor}" '
                              f'xml:space="preserve">{_tspans(text)}</text>')
        self.grow(x + x0, y + y0)
        self.grow(x + x1, y + y1)


def _draw(sch: Schematic, solution) -> Svg:
    canvas = _Canvas()
    paths = []
    for w in sch.wires:
        (x, y), *rest = [(px * GRID, py * GRID) for px, py in w.points]
        paths.append(f"M{x:g} {y:g}" + "".join(f"L{a:g} {b:g}" for a, b in rest))
        for px, py in w.points:
            canvas.grow(px * GRID, py * GRID)
    for px, py in _junctions(sch):
        canvas.items.append(f'<circle class="dot" cx="{px * GRID}" cy="{py * GRID}" r="3"/>')

    # everything a text should not cover: wires and the bodies of elements
    obstacles = [((a[0] * GRID, a[1] * GRID), (b[0] * GRID, b[1] * GRID)) for w in sch.wires for a, b in w.segments()]
    for e in sch.elements:
        ps = [(px * GRID, py * GRID) for px, py in e.pins()]
        obstacles += list(zip(ps, ps[1:]))

    placed: list[tuple] = []  # boxes of texts already on the page
    for e in sch.elements:
        x, y = e.at[0] * GRID, e.at[1] * GRID
        rotation = 0 if e.kind in UPRIGHT else e.rotation
        canvas.items.append(f'<g class="w" transform="translate({x:g} {y:g}) rotate({rotation})">{SYMBOLS[e.kind]}</g>')
        pins = [(px * GRID, py * GRID) for px, py in e.pins()]
        for px, py in pins:
            canvas.grow(px - 12, py - 12)
            canvas.grow(px + 12, py + 22)
        if e.kind == "label":
            canvas.text(x, y - 4, UP, [(e.text or "", "node")])
            continue
        if KINDS[e.kind].component is None:
            continue
        cx, cy = (sum(p[0] for p in pins) / len(pins), sum(p[1] for p in pins) / len(pins))
        if e.kind in LETTERS:
            canvas.items.append(f'<text class="letter" x="{cx:g}" y="{cy:g}">{LETTERS[e.kind]}</text>')
        axis = {0: RIGHT, 90: DOWN, 180: LEFT, 270: UP}[e.rotation]
        label_side, result_side = label_sides(axis)
        label = _label_lines(e, solution)
        results = _result_lines(e, solution, axis) if solution is not None else []
        own = list(zip(pins, pins[1:]))  # the element's own body is not in the way of its texts
        others = [s for s in obstacles if s not in own]

        def boxes(label_at: Vec, results_at: Vec):
            for side, lines in ((label_at, label), (results_at, results)):
                if lines:
                    ax, ay = cx + side[0] * BODY, cy + side[1] * BODY
                    x0, x1, y0, y1 = _text_box(side, lines)
                    yield (ax + x0, ax + x1, ay + y0, ay + y1)

        def clashes(label_at: Vec, results_at: Vec) -> int:
            return sum(_hits(b, others, placed) for b in boxes(label_at, results_at))

        if clashes(result_side, label_side) < clashes(label_side, result_side):  # swap sides if that is clearer
            label_side, result_side = result_side, label_side
        placed.extend(boxes(label_side, result_side))
        canvas.text(cx + label_side[0] * BODY, cy + label_side[1] * BODY, label_side, label)
        canvas.text(cx + result_side[0] * BODY, cy + result_side[1] * BODY, result_side, results)

    margin = 12
    left, top = min(canvas.xs) - margin, min(canvas.ys) - margin
    width = max(canvas.xs) - min(canvas.xs) + 2 * margin
    height = max(canvas.ys) - min(canvas.ys) + 2 * margin
    body = f'<path class="w" d="{"".join(paths)}"/>' + "".join(canvas.items + canvas.cards + canvas.texts)
    return Svg(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{left:g} {top:g} {width:g} {height:g}" '
        f'width="{width:g}" height="{height:g}"><style>{STYLE}</style>{body}</svg>'
    )
