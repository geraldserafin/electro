"""What the example notebooks are built with (apps/notebook/examples/<course>/NN-name.electro.json):
a ``Lesson`` of Markdown, code and drawings, written as plain data; a ``Drawing`` placed by hand on the
grid, its wires drawn by hand or routed between pins (``connect``). ``run.ts`` then runs each through the
notebook's kernel as "Run all" would (so it opens with its results) and checks its drawings. Run from the
repo root in devenv shell: ``python apps/notebook/scripts/examples/make.py``."""

from __future__ import annotations

import hashlib
import heapq
import json
from dataclasses import dataclass, field, replace
from pathlib import Path

EXAMPLES = Path(__file__).parents[2] / "examples"
SKETCHES = Path(__file__).parent / "sketches"
SYMBOLS = json.loads((Path(__file__).parents[2] / "src/features/schematic/symbols.json").read_text(encoding="utf-8"))
DATE = "2026-10-01T00:00:00Z"
WRITTEN: list[Path] = []
"""Every lesson saved, for ``run.ts`` to run."""


def sketch(name: str) -> str:
    """A sketch from scripts/examples/sketches/."""
    return (SKETCHES / name).read_text(encoding="utf-8")


def _id(*parts) -> str:
    """Ids that stay the same when the lesson is built again (the file changes only where it did)."""
    return hashlib.sha1("/".join(map(str, parts)).encode()).hexdigest()


def course(slug: str, title: str, description: str) -> None:
    folder = EXAMPLES / slug
    folder.mkdir(parents=True, exist_ok=True)
    text = json.dumps({"title": title, "description": description}, ensure_ascii=False, indent=1)
    (folder / "course.json").write_text(text + "\n", encoding="utf-8")


def _rotated(x: float, y: float, rotation: int) -> tuple[float, float]:
    for _ in range(rotation // 90 % 4):
        x, y = -y, x
    return x, y


@dataclass
class PartPin:
    name: str
    side: str  # "left", "right", "top", "bottom"
    at: int  # grid squares from the top (left, right) or the left (top, bottom)


@dataclass
class Part:
    """One's own component: a box of ``size`` with ``pins`` round it, ``schematic`` inside."""

    name: str
    size: tuple[int, int]
    pins: list[PartPin]
    schematic: Drawing

    def offsets(self) -> list[tuple[int, int]]:
        """Each pin's place, grid squares from the box's top left corner (as ``parts.ts``)."""
        w, h = self.size
        place = {"left": lambda a: (-1, a), "right": lambda a: (w + 1, a), "top": lambda a: (a, -1)}
        return [place.get(p.side, lambda a: (a, h + 1))(p.at) for p in self.pins]

    def to_data(self) -> dict:
        return {
            "name": self.name,
            "size": list(self.size),
            "pins": [{"name": p.name, "side": p.side, "at": p.at} for p in self.pins],
            "schematic": self.schematic.to_data(),
        }


@dataclass
class Element:
    """An element on the grid as the page keeps it (``ElementData``); ``definition``: a part's."""

    id: str
    kind: str
    at: tuple[int, int]
    rotation: int = 0
    value: str | None = None
    text: str | None = None
    definition: Part | None = field(default=None, repr=False)

    def pins(self) -> list[tuple[int, int]]:
        """Where its pins are (as ``model.ts``'s ``pins``)."""
        if self.definition is not None:
            offsets = self.definition.offsets()
        else:
            grid = SYMBOLS["grid"]
            offsets = [(px / grid, py / grid) for px, py in SYMBOLS["kinds"][self.kind]["pins"]]
        out = []
        for px, py in offsets:
            dx, dy = _rotated(px, py, self.rotation)
            out.append((round(self.at[0] + dx), round(self.at[1] + dy)))
        return out

    def to_data(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "at": list(self.at),
            "rotation": self.rotation,
            "value": self.value,
            "text": self.text,
        }


class Lesson:
    """A notebook: ``md``, ``code``, ``drawing`` / ``circuit`` in order, then ``save()``."""

    def __init__(self, course: str, name: str, title: str):
        self.course, self.name, self.title = course, name, title
        self.cells: list[dict] = []

    def _cell(self, cell: dict) -> dict:
        cell = {"id": _id(self.course, self.name, len(self.cells))[:8], **cell}
        self.cells.append(cell)
        return cell

    def md(self, text: str) -> None:
        self._cell({"type": "markdown", "source": text.strip()})

    def code(self, text: str, run: bool = True) -> None:
        """A code cell; ``run``: with its outputs (as after "Run all"), else left to the reader."""
        self._cell({"type": "code", "source": text.strip(), "outputs": [], "_run": run})

    def drawing(
        self, name: str, d: Drawing, *, joined=(), live: bool | None = None, solve: bool = False, exercise=False
    ) -> None:
        """A schematic cell with a hand-placed drawing. ``live``: it must run in time (default: unless it
        is solved on paper); ``solve``: solved on paper, its results on it; ``joined``: groups of (element
        id, pin index) that must be one point; ``exercise``: left unfinished on purpose (for the reader to
        finish), so not checked."""
        checks = None if exercise else {"live": not solve if live is None else live, "joined": joined, "nets": d.nets}
        self._cell({"type": "schematic", "name": name, "schematic": d.finish(), "_solve": solve, "_checks": checks})

    def circuit(self, name: str, code: str, *, solve: bool = False) -> None:
        """A schematic cell laid out from a circuit in code (the code view's way back)."""
        drawing = {"elements": [], "wires": []}
        self._cell({"type": "schematic", "name": name, "schematic": drawing, "_code": code, "_solve": solve})

    def save(self, *, errors_ok: bool = False) -> Path:
        """Written as it is; ``run.ts`` runs it (``errors_ok``: its code may fail, on purpose)."""
        notebook = json.dumps(
            {
                "format": "electro-notebook",
                "version": 2,
                "id": _id(self.course, self.name)[:16],
                "title": self.title,
                "created": DATE,
                "modified": DATE,
                "settings": {"codeInPdf": True},
                "cells": self.cells,
                **({"_errors_ok": True} if errors_ok else {}),
            },
            ensure_ascii=False,
            indent=2,
        )
        path = EXAMPLES / self.course / f"{self.name}.electro.json"
        path.write_text(notebook + "\n", encoding="utf-8")
        WRITTEN.append(path)
        print(path.relative_to(EXAMPLES.parent), len(self.cells), "cells")
        return path


class Drawing:
    """Elements and wires on the grid; ``label(text, at)`` puts a net label (same text: the same node,
    "GND": ground)."""

    def __init__(self):
        self.elements: list[Element] = []
        self.wires: list[list] = []
        self.labels = 0
        self.nets: dict[str, list] = {}
        self.parts: dict[str, Part] = {}  # one's own components on it, by key

    def add(self, *args) -> Element:
        e = Element(*args)
        if e.kind == "part":
            e.definition = self.parts[e.text or ""]
        self.elements.append(e)
        return e

    def wire(self, *points):
        self.wires.append(list(points))

    def label(self, text, at):
        self.labels += 1
        self.add(f"lbl{self.labels}", "label", at, 0, None, text)

    def ground(self, at):
        self.labels += 1
        self.add(f"gnd{self.labels}", "ground", at, 0)

    def stub(self, pin, towards, length, text):
        """A short wire from ``pin`` ``towards`` (dx, dy), and at its end the label ``text`` (None: ground)."""
        end = (pin[0] + towards[0] * length, pin[1] + towards[1] * length)
        self.wire(pin, end)
        if text is None:
            self.ground(end)
        else:
            self.label(text, end)

    def pin(self, id: str, k: int):
        return next(e for e in self.elements if e.id == id).pins()[k]

    def connect(self, nets: dict[str, list]):
        """Wires for the nets (name → [(element id, pin index), …]), routed (Router); checked by ``run.ts``."""
        self.nets |= nets
        Router(self).route(nets)

    def to_data(self) -> dict:
        data: dict = {
            "elements": [e.to_data() for e in self.elements],
            "wires": [{"points": [list(p) for p in w]} for w in self.wires],
        }
        if self.parts:
            data["parts"] = {key: part.to_data() for key, part in self.parts.items()}
        return data

    def finish(self) -> dict:
        """Moved to where a drawing starts: every point a few squares from the top left (a symbol may reach
        5 squares above its pins, as an HC-SR04's)."""
        points = [p for e in self.elements for p in e.pins()] + [p for w in self.wires for p in w]
        dx, dy = 4 - min(x for x, _ in points), 7 - min(y for _, y in points)
        self.elements = [replace(e, at=(e.at[0] + dx, e.at[1] + dy)) for e in self.elements]
        self.wires = [[(x + dx, y + dy) for x, y in w] for w in self.wires]
        return self.to_data()


# ------------------------------------------------------------------ wires routed between pins

# where a module's body is (rotation 0, grid squares from its first pin, both ends in): no wire goes there
BODIES = {
    "arduino": (1, 17, 1, 7),
    "servo": (1, 5, -1, 3),
    "seven_segment": (0, 4, 1, 5),
    "rgb_led": (1, 3, -1, 5),
    "lcd1602": (0, 15, 1, 6),
    "ultrasonic": (-2, 5, -2, 3),
    "lcd1602_i2c": (1, 18, -2, 4),
    "ssd1306": (-4, 7, 1, 8),
    "ds1307": (1, 6, -2, 4),
    "potentiometer": (1, 3, -1, 0),
    "passive_buzzer": (1, 3, -1, 0),
    "pico": (1, 7, -2, 16),
    "ili9341": (1, 21, -3, 12),
}
BEND = 4  # a bend costs as much as this many squares of wire


class Router:
    """Wires for nets on a drawing, along the grid: around the bodies and the other nets' pins, a net's
    wire never along another's and across one only at right angles (never at its bend or end); a net
    of several pins a tree — a branch ends on the wire it joins, which is split there (wires join
    only at their ends)."""

    def __init__(self, d: Drawing):
        self.d = d
        self.blocked: set = set()
        for e in d.elements:
            if e.kind in BODIES:
                assert e.rotation == 0, e.id
                x0, x1, y0, y1 = BODIES[e.kind]
                ax, ay = e.at
                self.blocked |= {(ax + x, ay + y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)}
            if e.kind == "part":  # one's own component: its box
                (w, h), (ax, ay) = e.definition.size, e.at
                assert e.rotation == 0, e.id
                self.blocked |= {(ax + x, ay + y) for x in range(w + 1) for y in range(h + 1)}
            pins = e.pins()
            if len(pins) == 2:  # a two-pin element: its body lies between its pins
                (x0, y0), (x1, y1) = pins
                self.blocked |= {(x0 + (x1 - x0) * k // 4, y0 + (y1 - y0) * k // 4) for k in (1, 2, 3)}
            if e.kind == "ground":
                self.blocked |= {(e.at[0] + dx, e.at[1] + 1) for dx in (-1, 0, 1)}
        self.pins = {p for e in d.elements for p in e.pins()}
        self.edges: set = set()  # grid edges taken
        self.through: dict = {}  # a point a wire goes straight through → "h" / "v"
        self.corners: set = set()  # wires' bends and ends
        self.crossed: set = set()  # where one net's wire crosses another's
        xs = [p[0] for p in self.blocked | self.pins]
        ys = [p[1] for p in self.blocked | self.pins]
        self.box = (min(xs) - 6, max(xs) + 6, min(ys) - 6, max(ys) + 6)

    def route(self, nets: dict[str, list]) -> dict:
        """nets: name → [(element id, pin index), …]; the wires are added to the drawing. Returns name → points."""
        at = {e.id: e.pins() for e in self.d.elements}
        points = {name: [at[i][k] for i, k in pins] for name, pins in nets.items()}
        mine = {p: name for name, ps in points.items() for p in ps}
        # the short ones first: they have the fewest ways round
        for name in sorted(
            points, key=lambda n: sum(abs(p[0] - q[0]) + abs(p[1] - q[1]) for p in points[n] for q in points[n])
        ):
            ps = points[name]
            reached = {ps[0]}
            wires: list[list] = []  # each a list of every grid point it passes
            for p in sorted(ps[1:], key=lambda p: min(abs(p[0] - q[0]) + abs(p[1] - q[1]) for q in reached)):
                if p in reached:  # on the net already (a pin on another's pin)
                    continue
                avoid = {q for q in self.pins if mine.get(q) != name or (q not in reached and q != p)}
                path = self.search(p, reached - self.crossed, avoid)
                assert path, f"no way for {name} to {p}"
                end = path[-1]
                for w in wires:  # the branch ends inside one of this net's wires: split it there
                    if end in w[1:-1]:
                        k = w.index(end)
                        wires.remove(w)
                        wires += [w[: k + 1], w[k:]]
                        self.corners.add(end)
                        self.through.pop(end, None)
                        break
                wires.append(path)
                reached |= set(path)
                self.take(self.corners_of(path))
            for w in wires:
                self.d.wire(*self.corners_of(w))
        return points

    @staticmethod
    def cells(wire):
        out = [wire[0]]
        for (x0, y0), (x1, y1) in zip(wire, wire[1:]):
            n = abs(x1 - x0) + abs(y1 - y0)
            out += [(x0 + (x1 - x0) * k // n, y0 + (y1 - y0) * k // n) for k in range(1, n + 1)]
        return out

    @staticmethod
    def corners_of(path):
        path = Router.cells(path) if len(path) > 1 else path
        keep = [path[0]]
        for a, b, c in zip(path, path[1:], path[2:]):
            if (b[0] - a[0], b[1] - a[1]) != (c[0] - b[0], c[1] - b[1]):
                keep.append(b)
        return keep + [path[-1]]

    def take(self, wire):
        cells = self.cells(wire)
        for a, b in zip(cells, cells[1:]):
            self.edges.add(frozenset((a, b)))
        corners = set(wire)
        self.corners |= corners
        for a, b in zip(cells, cells[1:-1]):
            if b not in corners:
                if b in self.through:
                    self.crossed.add(b)
                self.through[b] = "h" if a[1] == b[1] else "v"

    def search(self, start, targets, avoid):
        x0, x1, y0, y1 = self.box
        h = lambda p: min(abs(p[0] - t[0]) + abs(p[1] - t[1]) for t in targets)
        queue = [(h(start), 0, start, None, (start,))]
        best = {}
        while queue:
            _, cost, p, heading, path = heapq.heappop(queue)
            if p in targets and p != start:
                return list(path)
            if best.get((p, heading), 1e9) <= cost:
                continue
            best[(p, heading)] = cost
            crossing = p in self.through and p != start  # across another wire: straight on only
            for step in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if crossing and step != heading:
                    continue
                q = (p[0] + step[0], p[1] + step[1])
                if not (x0 <= q[0] <= x1 and y0 <= q[1] <= y1) or q in self.blocked or frozenset((p, q)) in self.edges:
                    continue
                if q in targets:
                    pass
                elif q in avoid or q in self.corners or q in path:
                    continue
                elif q in self.through and self.through[q] == ("h" if step[1] == 0 else "v"):
                    continue
                turn = heading is not None and step != heading
                heapq.heappush(queue, (cost + 1 + BEND * turn + h(q), cost + 1 + BEND * turn, q, step, path + (q,)))
        return None


# a board's pins by name → index (their order in symbols.json)
UNO = {f"D{i}": i for i in range(14)} | {f"A{i}": 14 + i for i in range(6)} | {"5V": 20, "GND": 21}
PICO = {f"GP{i}": i for i in range(23)} | {"GP26": 23, "GP27": 24, "GP28": 25, "VBUS": 26, "3V3": 27, "GND": 28}
A = lambda pin: ("ARD_1", UNO[pin])  # noqa: E731 — an Arduino's pin in a net
PI = lambda pin: ("PICO_1", PICO[pin])  # noqa: E731
