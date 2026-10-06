"""A problem as the page sends it: elements between named points, as data.

``{"elements": [{"id": "R_1", "kind": "resistor", "nodes": ["n1", "GND"], "value": "4.7k",
"params": {...}}, ...]}`` — ``id`` is the element's name, ``kind`` its kind's (``elements.BY_NAME``),
``nodes`` the points of its terminals in their order (``"GND"`` or ``"0"`` is ground; a terminal its
kind does not draw, ``gnd``, may be left out: it is ground), ``value`` its main parameter (left out or
``"?"``: to be found), ``params`` the others by name, ``part`` a real part's name (``elements.parts``) or an
LED's colour. A meter's value is its reading. ``given``: ``[[quantity, value], ...]``, conditions on
quantities; ``find``: quantities sought. A quantity is ``["I" | "U" | "P" | "value", element]``,
``["V", point]``, ``["U_between", point, point]`` or ``["sum", [[number, quantity], ...]]``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import sympy as sp

from electro.values import UNKNOWN, to_text

from ..circuit.elements import BY_NAME
from ..circuit.elements.parts import Part
from ..circuit.netlist import labels
from ..circuit.tree import GND, Circuit, Element, Net, Node, netlist
from ..circuit.wiring import at, beside
from ..solver.laws import reading
from .problem import Key, Problem
from .quantities import Across, Current, Parameter, Potential, Power, Quantity, Scaled, Sum, Voltage

GROUND_NAMES = ("GND", "0")

MODELS = {"opamp": "opamp_model"}
"""A kind that, given a real part, is that part's model."""


class UnknownKind(KeyError):
    def __init__(self, kind: str) -> None:
        super().__init__(kind)
        self.kind, self.available = kind, sorted(BY_NAME)


class WrongNodeCount(ValueError):
    def __init__(self, element: str, terminals: int, nodes: list[str]) -> None:
        super().__init__(element)
        self.part, self.terminals, self.nodes = element, terminals, nodes


@dataclass(frozen=True)
class Netlist:
    """The problem, and its elements and points by their names."""

    problem: Problem
    elements: dict[str, Element]
    points: dict[str, Node | Net]


def from_netlist(data: Mapping) -> Netlist:
    points: dict[str, Node | Net] = dict.fromkeys(GROUND_NAMES, GND)
    elements: dict[str, Element] = {}
    placed: list[Circuit] = []
    given: dict[Key, object] = {}
    for item in data["elements"]:
        e = _element(item)
        elements[item["id"]] = e
        names = _nodes(item, e)
        placed.append(at(e, *(points.setdefault(n, Node(n)) for n in names)))
        given |= _given(item, e)
    for q, value in data.get("given") or ():
        given[quantity(q, elements, points)] = value
    find = [quantity(q, elements, points) for q in data.get("find") or ()]
    return Netlist(Problem(beside(*placed), given, find), elements, points)


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
    kind = BY_NAME.get(MODELS.get(name, name) if item.get("part") else name)
    if kind is None:
        raise UnknownKind(item["kind"])
    return kind(item["id"])


def _nodes(item: Mapping, e: Element) -> list[str]:
    names = list(e.kind.grounded(tuple(str(n) for n in item["nodes"]), "GND"))
    terminals = e.kind.terminals
    if len(names) != len(terminals):
        raise WrongNodeCount(item["id"], len(terminals), names)
    return names


def _given(item: Mapping, e: Element) -> dict[Key, object]:
    out: dict[Key, object] = {}
    value = item.get("value")
    if value not in (None, "", "?"):
        reads = reading(e.kind)
        out[reads(e) if reads else e] = value
    params = item.get("params") or {}
    part = item.get("part")
    if part and not params and e not in out:
        out[e] = Part(part)
    elif part or params:
        out[e] = {**({"": value} if e in out else {}), **(Part(part).parameters(e.kind.name) if part else {}), **params}
    return out


def to_netlist(problem: Problem) -> dict:
    """The problem as data, read back by ``from_netlist``: each element named by its label, each point by
    its ``Node``'s or ``Net``'s name, the others ``n1``, ``n2``…"""
    net = netlist(problem.circuit)
    ids = labels(net)
    names = point_names(net)
    by = {e: id for id, (e, _) in zip(ids, net.parts)}

    def q(x) -> list:
        return quantity_data(x, by, {p: names[n] for n, p in net.named})

    readings = {r(e): e for e, _ in net.parts if (r := reading(e.kind))}
    elements = [
        {"id": id, "kind": e.kind.name, "nodes": [names[n] for n in ns], **_value(_given_of(problem, e))}
        for id, (e, ns) in zip(ids, net.parts)
    ]
    given = [[q(k), to_text(v)] for k, v in problem.given.items() if isinstance(k, Quantity) and k not in readings]
    return {"elements": elements, "given": given, "find": [q(x) for x in problem.find]}


def _given_of(problem: Problem, e: Element) -> object:
    """What is given of an element: its value, or a meter's reading."""
    reads = reading(e.kind)
    return problem.given.get(reads(e)) if reads else problem.given.get(e)


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


def point_names(net) -> list[str]:
    """Each point's name: its ``Node``'s or ``Net``'s, else ``n1``, ``n2``…"""
    named = {n: p.name if isinstance(p, Net) else p.label for n, p in net.named}
    taken = {x for x in named.values() if x}
    out, k = [], 0
    for n in range(net.size):
        if named.get(n):
            out.append(named[n])
            continue
        k += 1
        while f"n{k}" in taken:
            k += 1
        out.append(f"n{k}")
    return out


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
