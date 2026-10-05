"""Quantities by the names one writes: ``I_R_1``, ``U_R_1``, ``P_R_1`` (an element's current, voltage,
power), ``V_A`` (a point's potential), ``R_1`` (an element's value); expressions of them (``U_E_1 / I_E_1``),
read without ``eval``."""

from __future__ import annotations

from collections.abc import Callable, Mapping

import sympy as sp

from electro.values import expression

from ..circuit.tree import Element, Net, Node
from .quantities import Current, Parameter, Potential, Power, Quantity, Voltage

OF_ELEMENTS = {"I": Current, "U": Voltage, "P": Power}


class NoSuchQuantity(KeyError):
    def __init__(self, name: str, available: list[str]) -> None:
        super().__init__(name)
        self.name, self.available = name, available


def named(name: str, elements: Mapping[str, Element], points: Mapping[str, Node | Net]) -> Quantity:
    if name in elements:
        return Parameter(elements[name])
    letter, _, rest = name.partition("_")
    if letter in OF_ELEMENTS and rest in elements:
        return OF_ELEMENTS[letter](elements[rest])
    if letter == "V" and rest in points:
        return Potential(points[rest])
    raise NoSuchQuantity(name, names(elements, points))


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
