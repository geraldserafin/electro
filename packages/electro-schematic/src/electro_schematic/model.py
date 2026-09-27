"""A schematic drawing: elements and wires on a grid.

This is one more syntax for a circuit: two pins (or wire ends) on the same grid point
are connected, exactly like two terminals with the same node name in ``net(...)``.
Wires connect only with their ends (as in KiCad): a wire merely passing over a pin
or crossing another wire does not connect to it.
Gluing by coordinates is the same colimit as gluing by names, so ``to_circuit`` just
builds a netlist and the core solves it like any other circuit.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field

from electro import circuit as ct
from electro import components as comp
from electro.values import parse

Point = tuple[int, int]  # grid units; x to the right, y down (like the screen)
GRID = 20  # suggested pixels per grid unit, for renderers and editors


@dataclass(frozen=True)
class Kind:
    """Everything a layout or editor needs to know about an element kind (not its looks)."""

    pins: tuple[Point, ...]  # at rotation 0, relative to the element's origin (= its first pin)
    component: type | None = None  # electro component class; None for ground / label / terminal


TWO_PINS = ((0, 0), (4, 0))

KINDS: dict[str, Kind] = {
    "resistor": Kind(TWO_PINS, comp.Resistor),
    "capacitor": Kind(TWO_PINS, comp.Capacitor),
    "inductor": Kind(TWO_PINS, comp.Inductor),
    "voltage_source": Kind(TWO_PINS, comp.VoltageSource),
    "current_source": Kind(TWO_PINS, comp.CurrentSource),
    "ammeter": Kind(TWO_PINS, comp.Ammeter),
    "voltmeter": Kind(TWO_PINS, comp.Voltmeter),
    "hole": Kind(TWO_PINS, comp.Hole),
    "opamp": Kind(((0, 2), (0, 0), (4, 1)), comp.OpAmp),  # plus, minus, out (terminal order)
    "ground": Kind(((0, 0),)),
    "label": Kind(((0, 0),)),  # net label: same text = same node
    "terminal": Kind(((0, 0),)),  # an open end
}


def kind_of(component: comp.Component) -> str:
    for name, kind in KINDS.items():
        if kind.component is type(component):
            return name
    raise KeyError(f"Brak rodzaju elementu dla {type(component).__name__} — dodaj go do KINDS.")


def rotate(p: Point, rotation: int) -> Point:
    """Clockwise on screen, in steps of 90°."""
    x, y = p
    for _ in range((rotation // 90) % 4):
        x, y = -y, x
    return (x, y)


@dataclass
class Element:
    id: str  # stable identity; for components it is also the label (R_1, E_2, ...)
    kind: str
    at: Point
    rotation: int = 0  # 0, 90, 180, 270 (clockwise); 180 on a source = reversed polarity
    value: str | None = None  # as typed: "4.7k", "R", None = unknown
    text: str | None = None  # net label name

    def __post_init__(self):
        self.at = tuple(self.at)
        if self.kind not in KINDS:
            raise ValueError(f"Nieznany rodzaj elementu {self.kind!r}. Dostępne: {', '.join(KINDS)}")
        if self.rotation % 90:
            raise ValueError("Obrót musi być wielokrotnością 90°.")
        self.rotation %= 360

    def pins(self) -> list[Point]:
        return [(self.at[0] + dx, self.at[1] + dy) for dx, dy in (rotate(p, self.rotation) for p in KINDS[self.kind].pins)]

    def component(self) -> comp.Component | None:
        cls = KINDS[self.kind].component
        if cls is None:
            return None
        if issubclass(cls, comp.NoValue):
            return cls(label=self.id)
        return cls(parse(self.value), label=self.id)


@dataclass
class Wire:
    points: list[Point]  # a polyline with horizontal and vertical segments

    def __post_init__(self):
        self.points = [tuple(p) for p in self.points]
        for (x1, y1), (x2, y2) in zip(self.points, self.points[1:]):
            if x1 != x2 and y1 != y2:
                raise ValueError(f"Przewód musi iść poziomo albo pionowo: {(x1, y1)} → {(x2, y2)}")

    def segments(self):
        return list(zip(self.points, self.points[1:]))


def on_segment(p: Point, a: Point, b: Point) -> bool:
    """Is ``p`` strictly inside the axis-aligned segment ``a``–``b``?"""
    (x, y), (x1, y1), (x2, y2) = p, a, b
    if x1 == x2 == x:
        return min(y1, y2) < y < max(y1, y2)
    if y1 == y2 == y:
        return min(x1, x2) < x < max(x1, x2)
    return False


@dataclass
class Schematic:
    elements: list[Element] = field(default_factory=list)
    wires: list[Wire] = field(default_factory=list)

    # ------------------------------------------------------------------ access

    def element(self, id: str) -> Element:
        for e in self.elements:
            if e.id == id:
                return e
        raise KeyError(f"Nie ma elementu {id!r} na schemacie.")

    def components(self) -> list[Element]:
        return [e for e in self.elements if KINDS[e.kind].component is not None]

    # ------------------------------------------------------------------ connectivity

    def nodes(self) -> dict[Point, object]:
        """Grid point → its node (a representative), for every pin and wire point.

        What connects (as in KiCad): pins on the same point; a wire end on a pin; a wire
        end that is *not* on a pin touching another wire (its end, corner or middle — a
        T-junction). A wire merely passing over a pin, or crossing another wire, does not.
        """
        parent: dict = {}

        def find(x):
            parent.setdefault(x, x)
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a, b):
            parent[find(a)] = find(b)

        pin_at: dict[Point, list] = {}
        for e in self.elements:
            for i, p in enumerate(e.pins()):
                pin_at.setdefault(p, []).append(("pin", e.id, i))
        for keys in pin_at.values():
            for k in keys:
                union(k, keys[0])
        for i, w in enumerate(self.wires):
            find(("wire", i))
            for end in (w.points[0], w.points[-1]):
                if end in pin_at:
                    union(("wire", i), pin_at[end][0])
        for i, w in enumerate(self.wires):
            for end in (w.points[0], w.points[-1]):
                if end in pin_at:
                    continue  # an end on a pin belongs to that pin
                for j, v in enumerate(self.wires):
                    if j != i and (end in v.points or any(on_segment(end, a, b) for a, b in v.segments())):
                        union(("wire", i), ("wire", j))
        by_label: dict[str, object] = {}
        for e in self.elements:
            name = "GND" if e.kind == "ground" else e.text if e.kind == "label" else None
            if name:
                key = pin_at[e.pins()[0]][0]
                if name in by_label:
                    union(key, by_label[name])
                by_label.setdefault(name, key)
        result = {p: find(keys[0]) for p, keys in pin_at.items()}
        for i, w in enumerate(self.wires):
            for p in w.points:
                result.setdefault(p, find(("wire", i)))
        return result

    def to_circuit(self) -> ct.Circuit:
        """The circuit this drawing shows, as a netlist (element ids become labels)."""
        nodes = self.nodes()
        names: dict[Point, str] = {}
        for e in self.elements:
            if e.kind == "ground":
                names[nodes[e.pins()[0]]] = ct.GROUND
        for e in self.elements:
            if e.kind == "label" and e.text:
                names.setdefault(nodes[e.pins()[0]], e.text)
        taken, k = set(names.values()), 0
        items = []
        for e in self.components():
            node_names = []
            for p in e.pins():
                root = nodes[p]
                if root not in names:
                    while f"n{k}" in taken or k == 0:
                        k += 1
                    names[root] = f"n{k}"
                    taken.add(names[root])
                node_names.append(names[root])
            items.append((e.component(), *node_names))
        if not items:
            raise ValueError("Schemat nie ma żadnych elementów.")
        return ct.net(*items)

    def to_code(self, name: str = "uklad") -> str:
        """The drawing as plain ``electro`` code (``+``/``|`` when possible, else ``net(...)``)."""
        from electro.codegen import code

        return code(self.to_circuit(), name)

    # ------------------------------------------------------------------ editing

    def move(self, id: str, to: Point) -> None:
        """Move an element; wires attached to its pins follow (with an elbow if needed)."""
        e = self.element(id)
        old = e.pins()
        e.at = tuple(to)
        self._drag(dict(zip(old, e.pins())))

    def rotate(self, id: str, by: int = 90) -> None:
        """Rotate an element about its middle; wires stay where they are.

        After 90° its pins come off their wires; after 180° they land on the same wire
        ends, swapped — the element is reversed in place (e.g. a source's polarity).
        """
        e = self.element(id)

        def middle():
            ps = e.pins()
            return (sum(p[0] for p in ps) / len(ps), sum(p[1] for p in ps) / len(ps))

        bx, by_ = middle()
        e.rotation = (e.rotation + by) % 360
        ax, ay = middle()
        e.at = (e.at[0] + round(bx - ax), e.at[1] + round(by_ - ay))

    def move_segment(self, wire: int, index: int, by: int) -> None:
        """Move segment ``index`` of a wire sideways by ``by``; its ends stay (corners are added)."""
        w = self.wires[wire]
        a, b = w.points[index], w.points[index + 1]
        shift = (lambda p: (p[0], p[1] + by)) if a[1] == b[1] else (lambda p: (p[0] + by, p[1]))
        moved = [shift(p) if i in (index, index + 1) else p for i, p in enumerate(w.points)]
        path = ([w.points[0]] if index == 0 else []) + moved + ([w.points[-1]] if index + 2 == len(w.points) else [])
        w.points = _simplify(path)

    def _drag(self, moved: dict[Point, Point]) -> None:
        for w in self.wires:
            for end in (0, -1):
                target = moved.get(w.points[end])
                if target is None or target == w.points[end]:
                    continue
                pts = list(w.points if end == -1 else w.points[::-1])
                prev, last = pts[-2], pts[-1]
                if len(pts) >= 3:  # slide the last segment along with the pin (no overlaps)
                    pts[-2] = (prev[0], target[1]) if prev[1] == last[1] else (target[0], prev[1])
                    pts[-1] = target
                else:  # a single segment: add a corner
                    corner = (target[0], prev[1])
                    pts = [prev, corner, target]
                w.points = _simplify(pts if end == -1 else pts[::-1])

    # ------------------------------------------------------------------ JSON

    def to_json(self) -> str:
        return json.dumps({"version": 1, **asdict(self)}, ensure_ascii=False)

    @classmethod
    def from_json(cls, text: str) -> Schematic:
        data = json.loads(text)
        return cls([Element(**e) for e in data["elements"]], [Wire(**w) for w in data["wires"]])


def _simplify(points: list[Point]) -> list[Point]:
    """Drop repeated points and middle points of straight runs."""
    out: list[Point] = []
    for p in points:
        if out and out[-1] == p:
            continue
        if len(out) >= 2 and (out[-2][0] == out[-1][0] == p[0] or out[-2][1] == out[-1][1] == p[1]):
            out[-1] = p
            continue
        out.append(p)
    return out
