"""What the example notebooks are built with (apps/notebook/examples/<course>/NN-name.electro.json):
a ``Lesson`` of Markdown, code and drawings, run through the notebook's kernel as "Run all" would
(so it opens with its results) and checked; a ``Drawing`` placed by hand on the grid, its wires
drawn by hand or routed between pins (``connect``). Run from the repo root with PYTHONPATH set
(devenv shell): ``python apps/notebook/scripts/examples/make.py``."""

from __future__ import annotations

import hashlib
import heapq
import json
from pathlib import Path

from electro_schematic import Element, Schematic, Wire, layout

EXAMPLES = Path(__file__).parents[2] / "examples"
SKETCHES = Path(__file__).parent / "sketches"
DATE = "2026-10-01T00:00:00Z"


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
        is solved on paper); ``solve``: solved on paper, its results on it; ``exercise``: left unfinished
        on purpose (for the reader to finish), so not checked."""
        sch = d.finish(name, joined, not solve if live is None else live, exercise)
        self._cell({"type": "schematic", "name": name, "schematic": json.loads(sch.to_json()), "_solve": solve})

    def circuit(self, name: str, circuit, *, solve: bool = False) -> None:
        """A schematic cell laid out from a circuit in code (electro_schematic.layout)."""
        sch = layout(circuit)
        self._cell({"type": "schematic", "name": name, "schematic": json.loads(sch.to_json()), "_solve": solve})

    def save(self, *, errors_ok: bool = False) -> Path:
        from electro_notebook import kernel

        kernel.reset()
        schematics = {c["name"]: json.dumps(c["schematic"]) for c in self.cells if c["type"] == "schematic"}
        for cell in self.cells:
            if cell["type"] == "code" and cell.pop("_run"):
                cell["outputs"] = json.loads(kernel.run(cell["source"], json.dumps(schematics)))
                bad = [o.get("data") for o in cell["outputs"] if o["type"] == "error"]
                assert errors_ok or not bad, f"{self.name}: {cell['source']}\n→ {bad}"
            if cell["type"] == "schematic" and cell.pop("_solve"):  # as if its run button was clicked
                cell.update(json.loads(kernel.simulate(json.dumps(cell["schematic"]))), stale=False)
                bad = [p for p in cell["problems"] if p["kind"] == "error"]
                assert not bad, f"{self.name}: {cell['name']} → {bad}"
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
            },
            ensure_ascii=False,
            indent=2,
        )
        path = EXAMPLES / self.course / f"{self.name}.electro.json"
        path.write_text(notebook + "\n", encoding="utf-8")
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
        self.parts: dict = {}  # one's own components on it (electro_schematic.Part), by key

    def add(self, *args) -> Element:
        e = Element(*args)
        if e.kind == "part":
            e.__dict__["_definition"] = self.parts[e.text]
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
        """Wires for the nets (name → [(element id, pin index), …]), routed (Router); checked in finish()."""
        self.nets |= nets
        Router(self).route(nets)

    def finish(self, name, joined=(), live=True, exercise=False) -> Schematic:
        # where the drawing starts: every point a few squares from the top left (a symbol may reach
        # 5 squares above its pins, as an HC-SR04's)
        points = [p for e in self.elements for p in e.pins()] + [p for w in self.wires for p in w]
        dx, dy = 4 - min(x for x, _ in points), 7 - min(y for _, y in points)
        self.elements = [
            Element(e.id, e.kind, (e.at[0] + dx, e.at[1] + dy), e.rotation, e.value, e.text) for e in self.elements
        ]
        self.wires = [[(x + dx, y + dy) for x, y in w] for w in self.wires]
        sch = Schematic(self.elements, [Wire(w) for w in self.wires], dict(self.parts))
        if exercise:
            return sch
        sch.to_circuit()  # it must be a circuit
        from electro.devices import Board

        if live:
            from electro_notebook import kernel

            compiled = json.loads(kernel.live(json.dumps(_problem(sch))))  # …that runs in time
            assert "error" not in compiled, (name, compiled.get("error"))
        names = sch.node_names()
        pins = {e.id: e.pins() for e in self.elements}
        for group in joined:  # (element id, pin index), all on one node
            nodes = {names.get(pins[i][k]) for i, k in group}
            assert len(nodes) == 1 and None not in nodes, (name, group, nodes)
        # each routed net on a node of its own: no wire crossing another has joined it
        found = {net: {names.get(pins[i][k]) for i, k in group} for net, group in self.nets.items()}
        for net, nodes in found.items():
            assert len(nodes) == 1 and None not in nodes, (name, net, nodes)
        assert len({next(iter(n)) for n in found.values()}) == len(found), (name, found)
        # every label and ground on a pin or a wire's end (on a bend or a wire's middle it joins nothing)
        ends = {p for w in self.wires for p in (w[0], w[-1])}
        pin_points = {p for e in self.elements if e.kind not in ("label", "ground", "port") for p in e.pins()}
        for e in self.elements:
            if e.kind in ("label", "ground", "port"):
                assert e.pins()[0] in ends | pin_points, (name, e.id, e.text, "joins nothing")
        # nothing left hanging: every pin of a component on a wire or another pin (a board's may be free)
        touched = {p for w in self.wires for p in (w[0], w[-1])}
        at = {}
        for e in self.elements:
            for p in e.pins():
                at[p] = at.get(p, 0) + 1
        for e in self.elements:
            if e.kind == "part" or e.component() is None or isinstance(e.component(), Board):
                continue
            for p in e.pins():
                assert p in touched or at[p] > 1, (name, e.id, "pin not connected", p)
        return sch


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


# a board's pins by name → index (electro_schematic: KINDS["arduino"], KINDS["pico"])
UNO = {f"D{i}": i for i in range(14)} | {f"A{i}": 14 + i for i in range(6)} | {"5V": 20, "GND": 21}
PICO = {f"GP{i}": i for i in range(23)} | {"GP26": 23, "GP27": 24, "GP28": 25, "VBUS": 26, "3V3": 27, "GND": 28}
A = lambda pin: ("ARD_1", UNO[pin])  # noqa: E731 — an Arduino's pin in a net
PI = lambda pin: ("PICO_1", PICO[pin])  # noqa: E731


def _problem(sch: Schematic) -> dict:
    """The drawing as the page sends it to be run (schematic/problem.ts)."""
    readings = {"potentiometer": "position", "photoresistor": "lux", "thermistor": "temperature"}
    elements = []
    for item in sch.drawn_netlist():
        kind, text = item["kind"], (item.pop("text") or "").strip()
        params: dict = {}
        if kind in ("led", "diode", "npn", "pnp", "opamp") and text:
            item["part"] = text
        elif kind in ("sine_source", "square_source"):
            words = text.split()
            if words and words[-1].endswith("%"):
                params["duty"] = float(words.pop().rstrip("%").replace(",", ".")) / 100
            if words and words[-1].endswith("°"):
                params["phase"] = words.pop().rstrip("°").replace(",", ".")
            params["f"] = " ".join(words).replace("Hz", "").strip() or ("50" if kind == "sine_source" else "1k")
        elif kind in ("switch", "button"):
            params["closed"] = 1 if text == "closed" else 0
        elif kind in readings and text:
            params[readings[kind]] = text.replace(",", ".")
        elements.append({**item, "params": params})
    return {"elements": elements}
