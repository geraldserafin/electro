"""Quantities by the names one writes: ``I_R_1``, ``U_R_1``, ``P_R_1`` (an element's current, voltage,
power), ``V_A`` (a point's potential), ``R_1`` (an element's value); expressions of them (``U_E_1 / I_E_1``),
read without ``eval``."""

from __future__ import annotations

from collections.abc import Callable, Mapping

import sympy as sp

from electro.values import expression

from ..circuit.netlist import labels, point_names
from ..circuit.tree import GND, Circuit, Element, Net, Node, netlist
from .quantities import Current, Parameter, Potential, Power, Quantity, Voltage

OF_ELEMENTS = {"I": Current, "U": Voltage, "P": Power}


class NoSuchQuantity(KeyError):
    def __init__(self, name: str, available: list[str]) -> None:
        super().__init__(name)
        self.name, self.available = name, available


def naming(circuit: Circuit) -> tuple[dict[str, Element], dict[str, Node | Net]]:
    """A circuit's elements by their labels (``R_1``), its named points by their names (ground ``GND``)."""
    net = netlist(circuit)
    names = point_names(net)
    return dict(zip(labels(net), (e for e, _ in net.parts))), {"GND": GND} | {names[n]: p for n, p in net.named}


def named(name: str, elements: Mapping[str, Element], points: Mapping[str, Node | Net]) -> Quantity:
    if name in elements:
        return Parameter(elements[name])
    letter, _, rest = name.partition("_")
    if letter in OF_ELEMENTS and rest in elements:
        return OF_ELEMENTS[letter](elements[rest])
    if letter == "V" and rest in points:
        return Potential(points[rest])
    raise NoSuchQuantity(name, names(elements, points))


def name_of(q: Quantity, elements: Mapping[Element, str], points: Mapping[Node | Net, str]) -> str:
    """``q``'s name, as ``named`` reads it: ``elements`` and ``points`` by their names."""
    match q:
        case Parameter(e, ""):
            return elements[e]
        case Current(e, None) | Voltage(e) | Power(e):
            letter = next(k for k, kind in OF_ELEMENTS.items() if isinstance(q, kind))
            return f"{letter}_{elements[e]}"
        case Potential(p):
            return f"V_{points[p]}"
    raise NoSuchQuantity(str(q), [])


def names(elements: Mapping[str, Element], points: Mapping[str, Node | Net]) -> list[str]:
    return [
        *(f"{letter}_{id}" for id in elements for letter in OF_ELEMENTS),
        *elements,
        *(f"V_{p}" for p in points if p != "0"),
    ]


def evaluated(
    text: str,
    value: Callable[[Quantity], sp.Expr],
    elements: Mapping[str, Element],
    points: Mapping[str, Node | Net],
) -> sp.Expr:
    """``text`` with each name's ``value``."""
    e = expression(text)
    return e.subs({s: value(named(s.name, elements, points)) for s in e.free_symbols if isinstance(s, sp.Symbol)})
