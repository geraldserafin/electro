"""A problem as plain data (JSON) and back. In memory an element and a point are themselves; written down
they need names — an element its place in the list, a point its number — and read back, fresh objects
take their places."""

from __future__ import annotations

from ..circuit import elements
from ..circuit.kind import Kind
from ..circuit.netlist import Netlist, Point
from ..circuit.tree import Element, Net, Node, netlist
from ..circuit.wiring import rebuild
from .problem import Key, Problem
from .quantities import Across, Current, Parameter, Potential, Quantity, Voltage

KINDS: dict[str, Kind] = {k.name: k for k in elements.ALL}
OF_ELEMENT = {Current: "I", Voltage: "U", Parameter: "value"}


def problem_to_data(p: Problem) -> dict:
    net = netlist(p.circuit)
    index = {id(e): k for k, (e, _) in enumerate(net.parts)}

    def quantity(q: Quantity) -> list:
        match q:
            case Current(e) | Voltage(e) | Parameter(e):
                return [OF_ELEMENT[type(q)], index[id(e)]]
            case Potential(at):
                return ["V", _number(net, at)]
            case Across(a, b):
                return ["U_between", _number(net, a), _number(net, b)]
        raise TypeError(q)

    def key(k: Key) -> list:
        match k:
            case Element():
                return ["element", index[id(k)]]
            case str():
                return ["name", k]
        return quantity(k)

    named = dict(net.named)
    return {
        "points": [_point_to_data(named.get(n)) for n in range(net.size)],
        "elements": [{"kind": e.kind.name, "name": e.name, "at": list(ns)} for e, ns in net.parts],
        "given": [[key(k), str(v)] for k, v in p.given.items()],
        "find": [quantity(q) for q in p.find],
    }


def problem_from_data(d: dict) -> tuple[Problem, list[Element]]:
    points = [Net(p["net"]) if "net" in p else Node(p.get("label")) for p in d["points"]]
    elements = [KINDS[e["kind"]](e["name"]) for e in d["elements"]]
    circuit = rebuild(((e, tuple(x["at"])) for e, x in zip(elements, d["elements"])), enumerate(points))

    def quantity(q: list) -> Quantity:
        match q:
            case ["I", k]:
                return Current(elements[k])
            case ["U", k]:
                return Voltage(elements[k])
            case ["value", k]:
                return Parameter(elements[k])
            case ["V", n]:
                return Potential(points[n])
            case ["U_between", a, b]:
                return Across(points[a], points[b])
        raise ValueError(q)

    def key(k: list) -> Key:
        match k:
            case ["element", i]:
                return elements[i]
            case ["name", n]:
                return n
        return quantity(k)

    return Problem(circuit, {key(k): v for k, v in d["given"]}, [quantity(q) for q in d["find"]]), elements


def _number(net: Netlist, at: Point) -> int:
    return next(n for n, q in net.named if q == at)


def _point_to_data(p: Point | None) -> dict:
    match p:
        case Net(name):
            return {"net": name}
        case Node(label):
            return {"label": label}
    return {}
