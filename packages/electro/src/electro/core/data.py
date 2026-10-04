"""A circuit and a problem as plain data (JSON) and back. In memory an element and a point are
themselves (their identity); written down they need names — an element by its place in the list, a
point by its number — and read back, fresh objects take their places."""

from __future__ import annotations

from .problem import Across, Current, Parameter, Potential, Problem, Quantity, Voltage
from .syntax import KINDS as ALL_KINDS
from .syntax import Element, Kind, Net, Node, netlist, rebuild

KINDS: dict[str, Kind] = {k.name: k for k in ALL_KINDS}
QUANTITIES = {Current: "I", Voltage: "U", Parameter: "value"}


def problem_to_data(p: Problem) -> dict:
    net = netlist(p.circuit)
    index = {id(e): k for k, (e, _) in enumerate(net.parts)}

    def quantity(q: Quantity) -> list:
        match q:
            case Current(e) | Voltage(e) | Parameter(e):
                return [QUANTITIES[type(q)], index[id(e)]]
            case Potential(at):
                return ["V", _point(net, at)]
            case Across(a, b):
                return ["U_between", _point(net, a), _point(net, b)]
        raise TypeError(q)

    return {
        "points": [
            {"net": q.name} if isinstance(q, Net) else {"label": q.label} if isinstance(q, Node) else {}
            for q in (dict(net.named).get(n) for n in range(net.size))
        ],
        "elements": [{"kind": e.kind.name, "name": e.name, "at": list(ns)} for e, ns in net.parts],
        "given": [
            [
                ["element", index[id(k)]]
                if isinstance(k, Element)
                else ["name", k]
                if isinstance(k, str)
                else quantity(k),
                str(v),
            ]
            for k, v in p.given.items()
        ],
        "find": [quantity(q) for q in p.find],
    }


def _point(net, at) -> int:
    return next(n for n, q in net.named if q == at)


def problem_from_data(d: dict) -> tuple[Problem, list[Element]]:
    points = [Net(p["net"]) if "net" in p else Node(p.get("label")) for p in d["points"]]
    elements = [KINDS[e["kind"]](e["name"]) for e in d["elements"]]
    circuit = rebuild(((e, tuple(x["at"])) for e, x in zip(elements, d["elements"], strict=True)), enumerate(points))

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

    def key(k: list):
        match k:
            case ["element", i]:
                return elements[i]
            case ["name", n]:
                return n
        return quantity(k)

    return Problem(circuit, {key(k): v for k, v in d["given"]}, [quantity(q) for q in d["find"]]), elements
