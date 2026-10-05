"""The elements of a first course: resistor, capacitor, inductor, independent sources."""

from __future__ import annotations

import sympy as sp

from ..kind import two_terminal
from ..time import D


def _voltage_source(U: sp.Expr, I: sp.Expr, E: sp.Symbol) -> sp.Expr:
    """Its + on its second end: V_b − V_a = E."""
    return U + E


def _current_source(U: sp.Expr, I: sp.Expr, J: sp.Symbol) -> sp.Expr:
    """It pushes J from its first end to its second."""
    return I - J


Resistor = two_terminal("resistor", "R", lambda U, I, R: U - R * I, positive=True)
Capacitor = two_terminal("capacitor", "C", lambda U, I, C: I - C * D(U), positive=True)
Inductor = two_terminal("inductor", "L", lambda U, I, L: U - L * D(I), positive=True)
VoltageSource = two_terminal("voltage_source", "E", _voltage_source)
CurrentSource = two_terminal("current_source", "J", _current_source)
