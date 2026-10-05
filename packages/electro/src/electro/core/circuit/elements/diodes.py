"""Diodes: Shockley's, and the textbook's two straight pieces of it."""

from __future__ import annotations

import sympy as sp

from ..kind import Case, Cases, Kind, Params, Terminals

V_T = sp.Rational(25852, 1000000)
"""The thermal voltage at 300 K."""


def _shockley(t: Terminals, p: Params) -> list[sp.Expr]:
    """I = I_S·(e^(U/(n·V_T)) − 1)."""
    u = t.V["a"] - t.V["b"]
    return [t.I["a"] - p["I_S"] * (sp.exp(u / (p["n"] * V_T)) - 1)]


def _on_or_off(t: Terminals, p: Params) -> Cases:
    """On: at its forward drop U_F, any current in. Off: no current, below U_F."""
    u, i, drop = t.V["a"] - t.V["b"], t.I["a"], p[""]
    return Cases((Case("on", (u - drop,), (i,)), Case("off", (i,), (drop - u,))))


Diode = Kind(
    "diode", "D", ("a", "b"), _shockley, parameters=("I_S", "n"), defaults=(("I_S", sp.Rational(1, 10**14)), ("n", 1))
)

DiodeDrop = Kind("diode_drop", "D", ("a", "b"), _on_or_off, defaults=(("", sp.Rational(7, 10)),))
"""The textbook's diode: its main parameter is its forward drop U_F, 0.7 V unless given."""
