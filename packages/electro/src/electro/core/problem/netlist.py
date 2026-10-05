"""A problem as the page sends it: elements between named points, as data.

``{"elements": [{"id": "R_1", "kind": "resistor", "nodes": ["n1", "GND"], "value": "4.7k",
"params": {...}}, ...]}`` — ``id`` is the element's name, ``kind`` its kind's (``elements.BY_NAME``),
``nodes`` the points of its terminals in their order (``"GND"`` or ``"0"`` is ground; a terminal its
kind does not draw, ``gnd``, may be left out: it is ground), ``value`` its main parameter (left out or
``"?"``: to be found), ``params`` the others by name. A meter's value is its reading.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from ..circuit.elements import BY_NAME
from ..circuit.tree import GND, Circuit, Element, Net, Node
from ..circuit.wiring import at, beside
from .problem import Key, Problem
from .quantities import I, U

READINGS = {"ammeter": I, "voltmeter": U}
"""Meters: what their value is a reading of."""

GROUND_NAMES = ("GND", "0")


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
    return Netlist(Problem(beside(*placed), given), elements, points)


def _element(item: Mapping) -> Element:
    kind = BY_NAME.get(item["kind"])
    if kind is None:
        raise UnknownKind(item["kind"])
    return kind(item["id"])


def _nodes(item: Mapping, e: Element) -> list[str]:
    names = [str(n) for n in item["nodes"]]
    terminals = e.kind.terminals
    if len(names) == len(terminals) - 1 and terminals[-1] == "gnd":
        names.append("GND")
    if len(names) != len(terminals):
        raise WrongNodeCount(item["id"], len(terminals), names)
    return names


def _given(item: Mapping, e: Element) -> dict[Key, object]:
    out: dict[Key, object] = {}
    value = item.get("value")
    if value not in (None, "", "?"):
        reading = READINGS.get(e.kind.name)
        out[reading(e) if reading else e] = value
    params = item.get("params") or {}
    if params:
        out[e] = {**({"": value} if e in out else {}), **params}
    return out
