"""A drawing as the page sends it — elements and the points their terminals are on — made into a circuit with
the combinators, and a circuit made in code back into that, for the page to lay out.

``{"elements": [{"id": "R_1", "kind": "resistor", "nodes": ["n1", "GND"], "value": "4.7k",
"params": {...}}, ...]}`` — ``id`` is the element's name, ``kind`` its kind's (``elements.BY_KIND``),
``nodes`` the points of its terminals in their order (``"GND"`` or ``"0"`` is ground; a terminal its
kind does not draw, ``gnd``, may be left out: it is ground — ``Element.ground``), ``value`` its main parameter
(left out or ``"?"``: to be found), ``params`` the others by name, ``part`` a real part's name
(``electro.parts``) or an LED's colour. A meter's value is its reading. ``given``: ``[[quantity, value], ...]``,
conditions on quantities; ``find``: quantities sought. A quantity is ``["I" | "U" | "P" | "value", element]``,
``["V", point]``, ``["U_between", point, point]`` or ``["sum", [[number, quantity], ...]]``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from functools import reduce
from operator import matmul

import sympy as sp
from electro import GND, Element, Net, Node, Part
from electro.circuit.names import names
from electro.circuit.quantities import Across, Current, Parameter, Potential, Power, Quantity, Scaled, Sum, Voltage
from electro.elements import BY_KIND
from electro.values import UNKNOWN

from .kinds import reading
from .text import to_text

GROUND_NAMES = ("GND", "0")

MODELS = {"opamp": "opamp_model"}
"""A kind that, given a real part, is that part's model."""


class UnknownKind(KeyError):
    def __init__(self, kind: str) -> None:
        super().__init__(kind)
        self.kind, self.available = kind, sorted(BY_KIND)


class WrongNodeCount(ValueError):
    def __init__(self, element: str, terminals: int, nodes: list[str]) -> None:
        super().__init__(element)
        self.part, self.terminals, self.nodes = element, terminals, nodes


@dataclass(frozen=True)
class Drawing:
    """A schematic cell: the circuit, its values, what is sought, and its elements and points by their names.
    Solved and run as a circuit is, its values in."""

    circuit: Element
    values: dict
    find: list[Quantity]
    elements: dict[str, Element]
    points: dict[str, Node | Net]

    def __getitem__(self, id: str) -> Element:
        return self.elements[id]

    def final(self, frame=None):
        return self.circuit.final(self.values, frame)

    def simulate(self, until: float = 1.0, dt: float | None = None, inputs=None):
        return self.circuit.simulate(self.values, until, dt, inputs)


def from_drawing(data: Mapping) -> Drawing:
    points: dict[str, Node | Net] = dict.fromkeys(GROUND_NAMES, GND)
    elements: dict[str, Element] = {}
    pieces: list[Element] = []
    values: dict = {}
    for item in data["elements"]:
        e = _element(item)
        elements[item["id"]] = e
        pieces.append(placed(e, [points.setdefault(n, Node(n)) for n in _nodes(item, e)]))
        values |= _given(item, e)
    for q, value in data.get("given") or ():
        values[quantity(q, elements, points)] = value
    find = [quantity(q, elements, points) for q in data.get("find") or ()]
    return Drawing(reduce(matmul, pieces), values, find, elements, points)


def quantity(data: list, elements: Mapping[str, Element], points: Mapping[str, Node | Net]) -> Quantity:
    match data:
        case ["I", str(id)]:
            return Current(elements[id])
        case ["U", str(id)]:
            return Voltage(elements[id])
        case ["P", str(id)]:
            return Power(elements[id])
        case ["value", str(id)]:
            return Parameter(elements[id])
        case ["V", str(n)]:
            return Potential(points[n])
        case ["U_between", str(a), str(b)]:
            return Across(points[a], points[b])
        case ["sum", list(terms)]:
            return Sum(tuple(Scaled(sp.sympify(k), quantity(q, elements, points)) for k, q in terms))
    raise ValueError(data)


def _element(item: Mapping) -> Element:
    name = str(item["kind"])
    kind = BY_KIND.get(MODELS.get(name, name) if item.get("part") else name)
    if kind is None:
        raise UnknownKind(item["kind"])
    return kind(item["id"])


def _nodes(item: Mapping, e: Element) -> list[str]:
    """Each end's point: of a kind on ground (``Element.ground``) all but its last terminal's, which may be
    given (as ground) or left out."""
    names = [str(n) for n in item["nodes"]]
    ends = len(e.terminals) - e.ground
    if e.ground and len(names) == ends + 1 and names[-1] in GROUND_NAMES:
        names = names[:-1]
    if len(names) != ends:
        raise WrongNodeCount(item["id"], ends, names)
    return names


def _given(item: Mapping, e: Element) -> dict:
    out: dict = {}
    value = item.get("value")
    if value not in (None, "", "?"):
        reads = reading(e)
        out[reads(e) if reads else e] = value
    params = item.get("params") or {}
    part = item.get("part")
    if part and not params and e not in out:
        out[e] = Part(part)
    elif part or params:
        out[e] = {**({"": value} if e in out else {}), **(Part(part).parameters(e.kind) if part else {}), **params}
    return out


def to_drawing(circuit: Element, values: Mapping | None = None, find=()) -> dict:
    """The circuit as data, read back by ``from_drawing``: each element named by its label, each point by its
    ``Node``'s or ``Net``'s name, the others ``n1``, ``n2``…"""
    values = values or {}
    n = names(circuit)
    by = {e: label for e, label in n.labels.items()}
    at = wiring(circuit)
    points = {p: str(v)[2:] for p, v in n.points.items()} | {GND: "GND"}

    def q(x) -> list:
        return quantity_data(x, by, points)

    readings = {r(e): e for e in circuit.members if (r := reading(e))}
    elements = [{"id": by[e], "kind": e.kind, "nodes": at[e], **_value(_given_of(values, e))} for e in circuit.members]
    given = [[q(k), to_text(v)] for k, v in values.items() if isinstance(k, Quantity) and k not in readings]
    return {"elements": elements, "given": given, "find": [q(x) for x in find]}


def wiring(circuit: Element) -> dict[Element, list[str]]:
    """Each element's terminals' points, by name: what ``>>`` glued, the same point (``GND`` ground, a named
    point its name, the others ``n1``, ``n2``…)."""
    parent: dict = {}

    def find(x):
        while parent.get(x, x) != x:
            x = parent[x]
        return x

    for a, b in circuit.rel.wires:
        parent[find(a)] = find(b)
    n = names(circuit)
    called = {find(p.potential): str(v)[2:] for p, v in n.points.items()} | {find(sp.Integer(0)): "GND"}
    taken, auto = set(called.values()), 0
    out = {}
    for e in circuit.members:
        ends = []
        for t in e.terminals:
            root = find(e.V[t])
            while root not in called:
                auto += 1
                if f"n{auto}" not in taken:
                    called[root] = f"n{auto}"
            ends.append(called[root])
        out[e] = ends
    return out


def rebuilt(circuit: Element, old: Element, new: Element) -> Element:
    """The circuit with ``new`` where ``old`` is, on the same points."""
    at = wiring(circuit)
    points: dict[str, Node | Net] = {str(v)[2:]: p for p, v in names(circuit).points.items()}
    points |= dict.fromkeys(GROUND_NAMES, GND)
    return reduce(
        matmul,
        (placed(new if e is old else e, [points.setdefault(n, Node(n)) for n in at[e]]) for e in circuit.members),
    )


def placed(e: Element, at: list[Node | Net]) -> Element:
    """``e`` on the points ``at``, one for each of its terminals (the last of one on ground left out)."""
    if e.ground and len(at) == len(e.terminals):
        at = at[:-1]
    return at[0] >> e >> at[1] if len(e.terminals) == 2 else e >> reduce(matmul, at)


def _given_of(values: Mapping, e: Element) -> object:
    """What is given of an element: its value, or a meter's reading."""
    reads = reading(e)
    return values.get(reads(e)) if reads else values.get(e)


def quantity_data(q, elements: Mapping[Element, str], points: Mapping[Node | Net, str]) -> list:
    match q:
        case Current(e):
            return ["I", elements[e]]
        case Voltage(e):
            return ["U", elements[e]]
        case Power(e):
            return ["P", elements[e]]
        case Parameter(e):
            return ["value", elements[e]]
        case Potential(p):
            return ["V", points[p]]
        case Across(a, b):
            return ["U_between", points[a], points[b]]
        case Sum(terms):
            return ["sum", [[float(t.factor), quantity_data(t.of, elements, points)] for t in terms]]
    raise TypeError(q)


def _value(given: object) -> dict:
    """An element's value, its other parameters, its part, as data."""
    if given is None or given is UNKNOWN:
        return {"value": None}
    if isinstance(given, Part):
        return {"value": None, "part": given.name}
    if isinstance(given, Mapping):
        main = given.get("")
        others = {w: to_text(v) for w, v in given.items() if w}
        return {"value": None if main in (None, UNKNOWN) else to_text(main), "params": others}
    return {"value": to_text(given)}
