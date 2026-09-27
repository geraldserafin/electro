"""A schematic drawing: elements and wires on a grid.

This is one more syntax for a circuit: two pins (or wire ends) on the same grid point
are connected, exactly like two terminals with the same node name in ``net(...)``.
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

    def nodes(self) -> dict[Point, Point]:
        """Grid point → representative point of its node (union–find over pins and wires)."""
        parent: dict[Point, Point] = {}

        def find(p):
            parent.setdefault(p, p)
            while parent[p] != p:
                parent[p] = parent[parent[p]]
                p = parent[p]
            return p

        def union(a, b):
            parent[find(a)] = find(b)

        pins = [p for e in self.elements for p in e.pins()]
        ends = [p for w in self.wires for p in (w.points[0], w.points[-1])]
        for p in pins:
            find(p)
        for w in self.wires:
            for a, b in w.segments():
                union(a, b)
                for p in pins + ends:  # T-junctions and pins touching a wire
                    if on_segment(p, a, b):
                        union(p, a)
        by_label: dict[str, Point] = {}
        for e in self.elements:
            name = "GND" if e.kind == "ground" else e.text if e.kind == "label" else None
            if name:
                p = e.pins()[0]
                if name in by_label:
                    union(p, by_label[name])
                by_label.setdefault(name, p)
        return {p: find(p) for p in list(parent)}

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

    # ------------------------------------------------------------------ editing

    def move(self, id: str, to: Point) -> None:
        """Move an element; wires attached to its pins follow (with an elbow if needed)."""
        e = self.element(id)
        old = e.pins()
        e.at = tuple(to)
        self._drag(dict(zip(old, e.pins())))

    def rotate(self, id: str, by: int = 90) -> None:
        """Rotate an element about its first pin; attached wires follow."""
        e = self.element(id)
        old = e.pins()
        e.rotation = (e.rotation + by) % 360
        self._drag(dict(zip(old, e.pins())))

    def _drag(self, moved: dict[Point, Point]) -> None:
        for w in self.wires:
            for end in (0, -1):
                target = moved.get(w.points[end])
                if target is None or target == w.points[end]:
                    continue
                pts = w.points if end == -1 else w.points[::-1]
                if len(pts) == 1:
                    pts = [target]
                else:
                    prev = pts[-2]
                    elbow = (prev[0], target[1]) if prev[0] == pts[-1][0] else (target[0], prev[1])
                    pts = pts[:-1] + [elbow, target]
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
