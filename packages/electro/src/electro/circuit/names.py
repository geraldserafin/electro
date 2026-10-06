"""Quantities by the names one writes: ``I_R_1``, ``U_R_1``, ``P_R_1`` (an element's current, voltage, power),
``V_A`` (a point's potential), ``R_1`` (an element's value); expressions of them (``U_E_1 / I_E_1``), read
without ``eval``."""

from __future__ import annotations

import sympy as sp

from ..values import expression
from .quantities import Current, Parameter, Potential, Power, Quantity, Voltage

OF_ELEMENTS = {"I": Current, "U": Voltage, "P": Power}


class NoSuchQuantity(KeyError):
    def __init__(self, name: str, available: list[str]) -> None:
        super().__init__(name)
        self.name, self.available = name, available


def named(name: str, names) -> Quantity:
    """The quantity ``name`` is, in a circuit of these ``names`` (``formula.names``)."""
    elements = {label: e for e, label in names.labels.items()}
    points = {str(v)[2:]: p for p, v in names.points.items()}
    if name in elements:
        return Parameter(elements[name])
    letter, _, rest = name.partition("_")
    if letter in OF_ELEMENTS and rest in elements:
        return OF_ELEMENTS[letter](elements[rest])
    if letter == "V" and rest in points:
        return Potential(points[rest])
    available = [*(f"{x}_{e}" for e in elements for x in OF_ELEMENTS), *elements, *(f"V_{p}" for p in points)]
    raise NoSuchQuantity(name, available)


def evaluated(text: str, solution) -> sp.Expr:
    """``text`` with each name's value in ``solution``."""
    e = expression(text)
    return e.subs({s: solution(named(s.name, solution.names)) for s in e.free_symbols if isinstance(s, sp.Symbol)})
