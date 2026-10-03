"""A schematic drawing: elements and wires on a grid.

This is one more syntax for a circuit: two pins (or wire ends) on the same grid point
are connected, exactly like two terminals with the same node name in ``net(...)``.
One's own components (``Part``: a drawing of its own, its ports the pins of a box) are
drawn as a box and, for solving and simulating, opened up: their insides joined in.
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
from electro import devices as dev
from electro.values import parse

from .issues import (
    BadRotation,
    EmptySchematic,
    NoKindFor,
    NotOnSchematic,
    PartInItself,
    SkewedWire,
    UnknownKind,
    UnknownPart,
)

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
    # controlled sources: the control side on the left (cp above cn), the output on the right (n below p)
    "vcvs": Kind(((0, 0), (0, 4), (4, 4), (4, 0)), comp.VCVS),
    "vccs": Kind(((0, 0), (0, 4), (4, 4), (4, 0)), comp.VCCS),
    "ccvs": Kind(((0, 0), (0, 4), (4, 4), (4, 0)), comp.CCVS),
    "cccs": Kind(((0, 0), (0, 4), (4, 4), (4, 0)), comp.CCCS),
    # p1, p2 (the primary, on the left), s2, s1 (the secondary): the turns ratio in ``value``
    "transformer": Kind(((0, 0), (0, 4), (4, 4), (4, 0)), comp.Transformer),
    # in time only (electro.devices): the value, where there is one, is in ``value``; the rest
    # (an LED's colour, a switch's position, a potentiometer's wiper, an Arduino's sketch) in ``text``
    "sine_source": Kind(TWO_PINS, dev.SineSource),  # the frequency in ``text``
    "square_source": Kind(TWO_PINS, dev.SquareSource),  # the frequency, then the duty if not 50 %: "1k 25%"
    "diode": Kind(TWO_PINS, dev.Diode),
    "led": Kind(TWO_PINS, dev.LED),
    "zener": Kind(TWO_PINS, dev.Zener),  # the breakdown voltage in ``value``
    "rgb_led": Kind(((0, 0), (0, 2), (0, 4), (4, 2)), dev.RGBLED),  # r, g, b on the left, the cathode on the right
    # a, b, c, d, e, f, g, dp, com — where a 5161AS has them: g f com a b on top, e d c dp below
    "seven_segment": Kind(((3, 0), (4, 0), (3, 6), (1, 6), (0, 6), (1, 0), (0, 0), (4, 6), (2, 0)), dev.SevenSegment),
    "photoresistor": Kind(TWO_PINS, dev.Photoresistor),  # the light (lux) in ``text``
    "thermistor": Kind(TWO_PINS, dev.Thermistor),  # the temperature (°C) in ``text``
    "buzzer": Kind(TWO_PINS, dev.Buzzer),
    "passive_buzzer": Kind(TWO_PINS, dev.PassiveBuzzer),
    "servo": Kind(((0, 0), (0, 1), (0, 2)), dev.Servo),  # signal, +, − (its cable's order)
    "ultrasonic": Kind(
        ((0, 4), (1, 4), (2, 4), (3, 4)), dev.Ultrasonic
    ),  # VCC, Trig, Echo, GND below; the distance (cm) in ``text``
    "lcd1602": Kind(tuple((i, 0) for i in range(16)), dev.LCD1602),  # its 16 pins in a row on top, VSS first
    # I²C modules: the address in ``text``
    "lcd1602_i2c": Kind(((0, 0), (0, 1), (0, 2), (0, 3)), dev.LCD1602I2C),  # GND, VCC, SDA, SCL down its left
    "ssd1306": Kind(((0, 0), (1, 0), (2, 0), (3, 0)), dev.SSD1306),  # GND, VCC, SCL, SDA on top
    "ds1307": Kind(((0, 0), (0, 1), (0, 2), (0, 3)), dev.DS1307),  # GND, VCC, SDA, SCL down its left
    # on SPI: VCC, GND, CS, RESET, DC, MOSI, SCK, LED, MISO down its left, as the module's header has them
    "ili9341": Kind(tuple((0, i) for i in range(9)), dev.ILI9341),
    "lamp": Kind(TWO_PINS, dev.Lamp),  # its rated power (W) in ``text``
    "motor": Kind(TWO_PINS, dev.Motor),
    "relay": Kind(((0, 0), (0, 4), (4, 4), (4, 0), (6, 0)), dev.Relay),  # coil a, b; com, nc, no
    # logic gates: the inputs on the left, the output on the right (no supply pins, as in logic diagrams)
    "not_gate": Kind(TWO_PINS, dev.NOT),
    "and_gate": Kind(((0, 0), (0, 2), (4, 1)), dev.AND),
    "nand_gate": Kind(((0, 0), (0, 2), (4, 1)), dev.NAND),
    "or_gate": Kind(((0, 0), (0, 2), (4, 1)), dev.OR),
    "nor_gate": Kind(((0, 0), (0, 2), (4, 1)), dev.NOR),
    "xor_gate": Kind(((0, 0), (0, 2), (4, 1)), dev.XOR),
    # flip-flops and a counter: the inputs on the left (the clock marked), the outputs on the right
    "dff": Kind(((0, 0), (0, 2), (4, 0), (4, 2)), dev.DFlipFlop),  # d, clk, q, nq
    "jkff": Kind(((0, 0), (0, 2), (0, 4), (4, 0), (4, 4)), dev.JKFlipFlop),  # j, clk, k, q, nq
    "counter": Kind(((0, 0), (0, 3), (4, 0), (4, 1), (4, 2), (4, 3)), dev.Counter),  # clk, reset, q0…q3
    "switch": Kind(TWO_PINS, dev.Switch),
    "button": Kind(TWO_PINS, dev.Button),
    "potentiometer": Kind(((0, 0), (4, 0), (2, -2)), dev.Potentiometer),  # a, b, wiper
    "npn": Kind(((0, 0), (3, -2), (3, 2)), dev.NPN),  # base, collector, emitter
    "pnp": Kind(((0, 0), (3, -2), (3, 2)), dev.PNP),
    "nmos": Kind(((0, 0), (3, -2), (3, 2)), dev.NMOS),  # gate, drain, source
    "pmos": Kind(((0, 0), (3, -2), (3, 2)), dev.PMOS),
    # gnd, trig, out, reset, ctrl, thr, dis, vcc (DIP order)
    "timer555": Kind(((2, 6), (0, 2), (6, 3), (4, 0), (4, 6), (0, 3), (0, 4), (2, 0)), dev.Timer555),
    # D0–D13 on top (D13 on the left, as on the board), A0–A5, 5V and GND below
    "arduino": Kind(
        tuple((16 - i if i < 8 else 15 - i, 0) for i in range(14))
        + tuple((9 + i, 8) for i in range(6))
        + ((3, 8), (5, 8)),
        dev.Arduino,
    ),
    # GP0–GP15 down its left; GP16–GP22, GP26–GP28 up its right, then VBUS, 3V3, GND at its top (the USB end)
    "pico": Kind(
        tuple((0, i) for i in range(16))
        + ((8, 15), (8, 14), (8, 12), (8, 11), (8, 10), (8, 9), (8, 8), (8, 6), (8, 5), (8, 4))
        + ((8, 0), (8, 1), (8, 2)),
        dev.Pico,
    ),
    "ground": Kind(((0, 0),)),
    "label": Kind(((0, 0),)),  # net label: same text = same node
    "terminal": Kind(((0, 0),)),  # an open end
    # in a component's own drawing: where it is connected from outside, by its name (``text``); on
    # its own, a net label
    "port": Kind(((0, 0),)),
    "part": Kind(()),  # one of one's own components: ``text`` names its definition (Schematic.parts)
    # what a drawing marks, not of the circuit: a current's arrow on a wire, a voltage's beside what it
    # is across — from ``at`` the way it points (``rotation``), named by ``text`` ("I_2", "U_1")
    # an arrow's ``of``: the element whose current (voltage) it is — then its ``value``, if any, a given
    # of the problem (the solver's data: I_R2 = 2), and with none the solved one shown by it
    "current_arrow": Kind(()),
    "mesh_current": Kind(()),  # in a loop (``at``): its current around it
    "voltage_arrow": Kind(()),  # ``span``: its length in grid units (4, an element's, by default)
}

ARROWS = ("current_arrow", "voltage_arrow")
# a loop's current (a mesh current): a round arrow inside it, clockwise (``flip``: the other way)
MARKS = (*ARROWS, "mesh_current")


def arrow_length(e: Element) -> int:
    """How long an arrow is drawn, in grid units: a current's 1, a voltage's as set (4 by default)."""
    return 1 if e.kind == "current_arrow" else max(1, min(40, e.span or 4))


def arrow_sign(arrow: Element, of: Element) -> int | None:
    """How an arrow's quantity is the element's own (its current a → b, its voltage V_a − V_b): 1, −1,
    or None when its direction says nothing of it. Along the element: a current's the way it points;
    a voltage's head at the higher potential (pointing to ``a``: U_ab > 0). Across it (a current's on a
    wire into it): into the element at its nearer pin, or out of it."""
    pins = of.pins()
    if len(pins) != 2:
        return None
    (ax, ay), (bx, by) = pins
    dx, dy = rotate((1, 0), arrow.rotation)
    along = dx * (bx - ax) + dy * (by - ay)
    if along:
        same = 1 if along > 0 else -1
        return same if arrow.kind == "current_arrow" else -same
    if arrow.kind != "current_arrow":
        return None
    n = arrow_length(arrow)
    tail = arrow.at
    head = (tail[0] + dx * n, tail[1] + dy * n)
    middle = ((tail[0] + head[0]) / 2, (tail[1] + head[1]) / 2)

    def far(p, q):
        return abs(p[0] - q[0]) + abs(p[1] - q[1])

    near = min(pins, key=lambda p: far(middle, p))
    into = far(head, near) < far(tail, near)
    return (1 if near == pins[0] else -1) * (1 if into else -1)


SIDES = ("left", "right", "top", "bottom")


@dataclass
class PartPin:
    name: str  # a port's name in the component's drawing
    side: str  # "left", "right", "top", "bottom"
    at: int  # grid squares along its side, from the top (left, right) or the left (top, bottom)


@dataclass
class Part:
    """One's own component: its box (``size``, grid squares), its pins around it, and what is inside
    (``schematic``, where a ``port`` of the pin's name is). Placed, the box's top left corner is the
    element's origin; each pin sticks out one square from its side."""

    name: str
    size: tuple[int, int]
    pins: list[PartPin]
    schematic: Schematic
    prefix: str = "U"

    def offsets(self) -> list[Point]:
        w, h = self.size
        where = {"left": lambda a: (-1, a), "right": lambda a: (w + 1, a), "top": lambda a: (a, -1)}
        return [where.get(p.side, lambda a: (a, h + 1))(p.at) for p in self.pins]

    @classmethod
    def from_dict(cls, data: dict) -> Part:
        return cls(
            data["name"],
            tuple(data["size"]),
            [PartPin(**p) for p in data["pins"]],
            Schematic.from_dict(data["schematic"]),
            data.get("prefix", "U"),
        )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "size": list(self.size),
            "pins": [asdict(p) for p in self.pins],
            "schematic": self.schematic.to_dict(),
            "prefix": self.prefix,
        }


def kind_of(component: comp.Component) -> str:
    for name, kind in KINDS.items():
        if kind.component is type(component):
            return name
    raise NoKindFor(type(component).__name__)


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
    text: str | None = (
        None  # net label name; or an LED's colour, a switch's position, a source's frequency, a sensor's reading, an Arduino's sketch
    )
    of: str | None = None  # an arrow's: the element whose current or voltage it is
    span: int | None = None  # a voltage arrow's: its length in grid units
    between: list | None = None  # a voltage arrow's between two points of the drawing ([[x, y], [x, y]]): tail, head
    flip: bool | None = None  # its label on the other side than it would be (the drawing's own look)

    def __post_init__(self):
        self.at = tuple(self.at)
        if self.kind not in KINDS:
            raise UnknownKind(self.kind, list(KINDS))
        if self.rotation % 90:
            raise BadRotation(self.rotation)
        self.rotation %= 360

    def pins(self) -> list[Point]:
        own = self.definition.offsets() if self.kind == "part" else KINDS[self.kind].pins
        return [(self.at[0] + dx, self.at[1] + dy) for dx, dy in (rotate(p, self.rotation) for p in own)]

    @property
    def definition(self) -> Part:
        """A part's: bound by the drawing it is on (Schematic.parts)."""
        found = self.__dict__.get("_definition")
        if found is None:
            raise UnknownPart(self.text or "")
        return found

    def component(self) -> comp.Component | None:
        cls = KINDS[self.kind].component
        if cls is None:
            return None
        if hasattr(cls, "from_schematic"):
            return cls.from_schematic(self.value, self.text, self.id)
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
                raise SkewedWire((x1, y1), (x2, y2))

    def segments(self):
        return list(zip(self.points, self.points[1:]))


def _unique(points: list[Point]) -> list[Point]:
    """A polyline's points without one repeated straight after itself."""
    return [p for k, p in enumerate(points) if not k or p != points[k - 1]]


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
    parts: dict[str, Part] = field(default_factory=dict)  # one's own components on it, by their key

    def __post_init__(self):
        self.bind()

    def bind(self) -> None:
        """Each part on the drawing given its definition."""
        for e in self.elements:
            if e.kind == "part":
                e.__dict__["_definition"] = self.parts.get(e.text or "")

    def __getattr__(self, name: str):
        """Anything else is the circuit's: ``drawing.solve(...)``, ``drawing.transpose()``, …"""
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self.to_circuit(), name)

    # ------------------------------------------------------------------ access

    def element(self, id: str) -> Element:
        for e in self.elements:
            if e.id == id:
                return e
        raise NotOnSchematic(id)

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
        # a terminal (a point a voltage is at) is on whatever wire it lies on, a corner or the middle too
        for e in self.elements:
            if e.kind == "terminal":
                (p,) = e.pins()
                for i, w in enumerate(self.wires):
                    if p in w.points or any(on_segment(p, a, b) for a, b in w.segments()):
                        union(("wire", i), pin_at[p][0])
        by_label: dict[str, object] = {}
        for e in self.elements:
            name = "GND" if e.kind == "ground" else e.text if e.kind in ("label", "port") else None
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
        items, _ = self._netlist_items()
        if not items:
            raise EmptySchematic()
        return ct.net(*items)

    def node_names(self) -> dict[Point, str]:
        """Every pin's and wire's grid point → the name of its node in ``to_circuit()`` (points of
        wires that touch no element have none)."""
        _, named = self._netlist_items()
        return named

    def _netlist_items(self, prefix: str = "", outside: dict[str, str] | None = None, within: tuple = ()):
        """The netlist's items (component, node names…) and every point's node name. Inside a part
        (``prefix``: its label and "_"), labels and elements are its own (prefixed), a port is the
        outside's node (``outside``: port name → node name), ground is everyone's."""
        nodes = self.nodes()
        names: dict[object, str] = {}
        for e in self.elements:
            if e.kind == "ground":
                names[nodes[e.pins()[0]]] = ct.GROUND
        if outside is not None:
            for e in self.elements:
                if e.kind == "port" and e.text in outside:
                    names.setdefault(nodes[e.pins()[0]], outside[e.text])
        for e in self.elements:
            if e.kind in ("label", "port") and e.text:
                names.setdefault(nodes[e.pins()[0]], prefix + e.text)
        # a terminal (a point a voltage is at): its node named by its id (its name may be any, twice too)
        for e in self.elements:
            if e.kind == "terminal":
                names.setdefault(nodes[e.pins()[0]], prefix + e.id)
        taken, k = set(names.values()), 0

        def name(p):
            nonlocal k
            root = nodes[p]
            if root not in names:
                while f"{prefix}n{k}" in taken or k == 0:
                    k += 1
                names[root] = f"{prefix}n{k}"
                taken.add(names[root])
            return names[root]

        items = []
        for e in self.elements:
            if e.kind == "part":
                d = e.definition
                if e.text in within or len(within) > 16:
                    raise PartInItself(e.text or "")
                ports = {pin.name: name(p) for pin, p in zip(d.pins, e.pins())}
                inner, _ = d.schematic._netlist_items(f"{prefix}{e.id}_", ports, (*within, e.text))
                items += inner
            elif KINDS[e.kind].component is not None:
                node_names = [name(p) for p in e.pins()]
                own = e if not prefix else Element(prefix + e.id, e.kind, e.at, e.rotation, e.value, e.text)
                items.append((own.component(), *node_names))
        return items, {p: names[root] for p, root in nodes.items() if root in names}

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

    def to_dict(self) -> dict:
        out = {
            "version": 1,
            "elements": [
                {k: v for k, v in asdict(e).items() if v is not None or k not in ("of", "span", "between", "flip")}
                for e in self.elements
            ],
            "wires": [{"points": [list(p) for p in w.points]} for w in self.wires],
        }
        if self.parts:
            out["parts"] = {key: part.to_dict() for key, part in self.parts.items()}
        return out

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    def quantities(self) -> list[tuple[Element, object]]:
        """What each of its marks is a quantity of, as an expression of the solver's symbols (``I_R1``,
        ``U_R1``, ``V_A``): a voltage arrow between two points V_head − V_tail; an arrow of an element
        (``of``) its current or voltage, as it points; a current's arrow on a wire the current along it
        (``current_along``); a loop's arrow its mesh current (``mesh_current``); a terminal's or a net
        label's its point's potential, against ground. Marks that say nothing (on no wire, wires in a
        loop) are left out."""
        import sympy as sp

        names = self.node_names()

        def potential(p) -> object:
            name = self.node_at(tuple(p), names)
            return sp.Integer(0) if name in (None, ct.GROUND) else sp.Symbol(f"V_{name}")

        def currents(terms: dict[str, int]) -> object:
            return sp.Add(*(k * sp.Symbol(f"I_{id}") for id, k in terms.items()))

        by_id = {e.id: e for e in self.elements}
        out = []
        for a in self.elements:
            if a.kind == "voltage_arrow" and a.between and len(a.between) == 2:
                tail, head = a.between
                out.append((a, potential(head) - potential(tail)))
            elif a.kind in ARROWS and a.of:
                of = by_id.get(a.of)
                sign = arrow_sign(a, of) if of is not None and KINDS[of.kind].component is not None else None
                if sign is not None:
                    out.append((a, sign * sp.Symbol(f"{'I' if a.kind == 'current_arrow' else 'U'}_{of.id}")))
            elif a.kind == "current_arrow" and not a.between:
                terms = self.current_along(a.at, rotate((1, 0), a.rotation))
                if terms is not None:
                    out.append((a, currents(terms)))
            elif a.kind == "mesh_current":
                terms = self.mesh_current(a.at)
                if terms is not None:
                    out.append((a, (-1 if a.flip else 1) * currents(terms)))
            elif a.kind == "terminal" or (a.kind == "label" and a.text):
                out.append((a, potential(a.at)))
        return out

    def current_along(self, at: Point, step: Point) -> dict[str, int] | None:
        """The current along a wire at ``at``, the way ``step`` (a unit step along it). By Kirchhoff's
        current law what flows on into the node beyond is what leaves that node through its elements:
        ``{id: ±1}`` — 1 for an element it goes into by its first pin (an element's own current, I_id, is
        from its first pin to its second), −1 by its second. None: no wire there; the wire's two sides
        joined some other way too (wires in a loop: no one current there); or an element of more pins
        than two beyond it."""
        head = (at[0] + step[0], at[1] + step[1])

        def on(p, a, b):
            return p in (a, b) or on_segment(p, a, b)

        found = next(
            (
                (i, k)
                for i, w in enumerate(self.wires)
                for k, (a, b) in enumerate(w.segments())
                if on(at, a, b) and on(head, a, b)
            ),
            None,
        )
        if found is None:
            return None
        i, k = found
        w = self.wires[i]
        # the wire cut there, between the two: its two pieces
        a, b = w.points[k], w.points[k + 1]
        first, second = (at, head) if (b[0] - a[0]) * step[0] + (b[1] - a[1]) * step[1] > 0 else (head, at)
        pieces = [
            Wire(ps)
            for ps in (_unique([*w.points[: k + 1], first]), _unique([second, *w.points[k + 1 :]]))
            if len(ps) > 1
        ]
        nodes = Schematic(self.elements, [*self.wires[:i], *pieces, *self.wires[i + 1 :]], self.parts).nodes()
        if at not in nodes:
            return {}  # a wire's loose end: nothing flows
        beyond = nodes[head]
        if nodes[at] == beyond:
            return None
        out: dict[str, int] = {}
        for e in self.elements:
            if KINDS[e.kind].component is None and e.kind != "part":
                continue
            ps = e.pins()
            for k, p in enumerate(ps):
                if nodes.get(p) == beyond:
                    if len(ps) != 2 or e.kind == "part":
                        return None
                    out[e.id] = out.get(e.id, 0) + (1 if k == 0 else -1)
        return {id: k for id, k in out.items() if k}

    def mesh_current(self, at: Point) -> dict[str, int] | None:
        """The mesh current of the loop ``at`` is in — the smallest one drawn around it — clockwise (on
        screen): ``{id: ±1}`` as ``current_along``. Each loop's current is the one around the loop next to
        it (out of the drawing: none) and the current of what is between them, the way it goes around:
        found so from outside in. None: in no loop, wires crossing (no loops to tell), or only through
        what has no one current (wires in a loop, an element of more pins) to get there."""
        import math

        plane = self._plane()
        if plane is None:
            return None
        half = [(u, v, tag) for u, v, tag in plane] + [(v, u, tag) for u, v, tag in plane]
        n = len(plane)
        twin = [(h + n) % (2 * n) for h in range(2 * n)]
        out: dict = {}
        for h, (u, _, _) in enumerate(half):
            out.setdefault(u, []).append(h)
        for u, hs in out.items():
            hs.sort(key=lambda h: math.atan2(half[h][1][1] - u[1], half[h][1][0] - u[0]))
        nxt = []
        for h, (_, v, _) in enumerate(half):
            hs = out[v]
            nxt.append(hs[(hs.index(twin[h]) - 1) % len(hs)])
        # the faces: their half-edges, and their area (positive: clockwise on screen)
        face_of = [-1] * (2 * n)
        faces = []
        for h in range(2 * n):
            if face_of[h] >= 0:
                continue
            face, g = [], h
            while face_of[g] < 0:
                face_of[g] = len(faces)
                face.append(g)
                g = nxt[g]
            area = sum(half[g][0][0] * half[g][1][1] - half[g][1][0] * half[g][0][1] for g in face) / 2
            faces.append((face, area))
        if not faces:
            return None
        outer_sign = math.copysign(1, max(faces, key=lambda f: abs(f[1]))[1])
        bounded = [i for i, (_, area) in enumerate(faces) if area and math.copysign(1, area) != outer_sign]

        def inside(face) -> bool:
            crossings = 0
            for g in face:
                (x1, y1), (x2, y2) = half[g][0], half[g][1]
                if (y1 > at[1]) != (y2 > at[1]) and at[0] < x1 + (at[1] - y1) * (x2 - x1) / (y2 - y1):
                    crossings += 1
            return crossings % 2 == 1

        around = [i for i in bounded if inside(faces[i][0])]
        if not around:
            return None
        target = min(around, key=lambda i: abs(faces[i][1]))
        sense = -int(outer_sign)  # 1: a bounded face's half-edges go clockwise

        def along(h) -> dict[str, int] | None:
            u, v, tag = half[h]
            if tag is None:
                return None
            if tag[0] == "element":
                first = self.element(tag[1]).pins()[0]
                return {tag[1]: 1 if u == first else -1}
            return self.current_along(u, ((v[0] > u[0]) - (v[0] < u[0]), (v[1] > u[1]) - (v[1] < u[1])))

        known: dict[int, dict[str, int]] = {i: {} for i in range(len(faces)) if i not in bounded}
        queue = list(known)
        while queue and target not in known:
            f = queue.pop(0)
            for h in faces[f][0]:
                g = face_of[twin[h]]
                if g in known:
                    continue
                current = along(twin[h])
                if current is None:
                    continue
                total = dict(known[f])
                for id, k in current.items():
                    total[id] = total.get(id, 0) + sense * k
                known[g] = {id: k for id, k in total.items() if k}
                queue.append(g)
        return known.get(target)

    def _plane(self) -> list[tuple] | None:
        """The drawing as a plane graph, its edges ``(u, v, tag)``: a wire's stretches between the points
        something is at (its corners and ends, pins, other wires' ends), tag ``("wire",)``; each two-pin
        element's body, from its first pin to its second, ``("element", id)``; an element of more pins,
        each pin to its middle, tag None (no one current there). None: wires crossing (not a plane)."""
        points = {p for w in self.wires for p in w.points} | {p for e in self.elements for p in e.pins()}
        segments = [s for w in self.wires for s in w.segments()]
        for a, b in segments:
            for c, d in segments:
                if a[1] == b[1] and c[0] == d[0]:  # one across, one down: crossing inside both
                    if on_segment((c[0], a[1]), a, b) and on_segment((c[0], a[1]), c, d):
                        return None
        edges = set()
        for a, b in segments:
            on = sorted(
                (p for p in points if p in (a, b) or on_segment(p, a, b)),
                key=lambda p: abs(p[0] - a[0]) + abs(p[1] - a[1]),
            )
            for p, q in zip(on, on[1:]):
                edges.add((min(p, q), max(p, q), ("wire",)))
        for e in self.elements:
            if KINDS[e.kind].component is None and e.kind != "part":
                continue
            ps = e.pins()
            if len(ps) == 2 and e.kind != "part":
                edges.add((ps[0], ps[1], ("element", e.id)))
            elif len(ps) > 1:
                middle = (sum(p[0] for p in ps) / len(ps), sum(p[1] for p in ps) / len(ps))
                edges.update((p, middle, None) for p in ps)
        return sorted(edges, key=str)

    def beside(self, arrow: Element) -> Point:
        """How far a voltage arrow between two points is drawn off its line (grid units): one square to the
        side its name is on (its left as it points; ``flip``: its right) when it would lie on what it is
        across — a two-pin element's body, a wire along it — as a book draws U_1 by R_1; else (0, 0)."""
        if arrow.kind != "voltage_arrow" or not arrow.between or len(arrow.between) != 2:
            return (0, 0)
        a, b = (tuple(p) for p in arrow.between)
        if a[0] != b[0] and a[1] != b[1]:
            return (0, 0)

        def on(p):
            return p in (a, b) or on_segment(p, a, b)

        def along(c, d) -> bool:
            k = 1 if a[1] == b[1] else 0  # the coordinate they share (a row: y)
            if not (c[k] == d[k] == a[k]):
                return False
            j = 1 - k
            return min(max(a[j], b[j]), max(c[j], d[j])) > max(min(a[j], b[j]), min(c[j], d[j]))

        across = any(
            KINDS[e.kind].component is not None and len(ps := e.pins()) == 2 and all(on(p) for p in ps)
            for e in self.elements
        ) or any(along(c, d) for w in self.wires for c, d in w.segments())
        if not across:
            return (0, 0)
        dx, dy = (b[0] > a[0]) - (b[0] < a[0]), (b[1] > a[1]) - (b[1] < a[1])
        side = -1 if arrow.flip else 1
        return (side * dy, -side * dx)

    def node_at(self, p: Point, names: dict[Point, str] | None = None) -> str | None:
        """The name of the node ``p`` is on in ``to_circuit()`` (a pin, a wire's point or anywhere along it);
        None: on nothing."""
        names = self.node_names() if names is None else names
        if p in names:
            return names[p]
        for w in self.wires:
            if any(on_segment(p, a, b) for a, b in w.segments()):
                return names.get(w.points[0])
        return None

    @classmethod
    def from_dict(cls, data: dict) -> Schematic:
        return cls(
            [Element(**e) for e in data["elements"]],
            [Wire(**w) for w in data["wires"]],
            {key: Part.from_dict(p) for key, p in (data.get("parts") or {}).items()},
        )

    @classmethod
    def from_json(cls, text: str) -> Schematic:
        return cls.from_dict(json.loads(text))


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
