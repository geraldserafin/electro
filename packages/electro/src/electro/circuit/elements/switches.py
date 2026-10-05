"""What a hand sets: a switch, a push button, a potentiometer."""

from __future__ import annotations

import sympy as sp

from ..kind import Kind, Params, Terminals
from ..time import when

POT_END = sp.Rational(1, 1000)
"""A potentiometer's track never ends in a short circuit (ohms)."""


def _switch(t: Terminals, p: Params) -> list[sp.Expr]:
    """Closed: no voltage across it. Open: no current through it."""
    return [when(p["closed"] > sp.Rational(1, 2), t.across("a", "b"), t.I["a"])]


def _potentiometer(t: Terminals, p: Params) -> list[sp.Expr]:
    """The track either side of the wiper ``w``, ``position`` of the way from ``a`` (0) to ``b`` (1)."""
    r, x = p[""], p["position"]
    return [t.across("a", "w") - (r * x + POT_END) * t.I["a"], t.across("b", "w") - (r * (1 - x) + POT_END) * t.I["b"]]


Switch = Kind("switch", "S", ("a", "b"), _switch, parameters=("closed",), defaults=(("closed", 0),), inputs=("closed",))
"""``closed``: 1 closed, 0 open."""

Button = Kind("button", "B", ("a", "b"), _switch, parameters=("closed",), defaults=(("closed", 0),), inputs=("closed",))
"""Closed while pressed."""

Potentiometer = Kind(
    "potentiometer",
    "P",
    ("a", "b", "w"),
    _potentiometer,
    parameters=("", "position"),
    defaults=(("position", sp.Rational(1, 2)),),
    positive=("",),
    inputs=("position",),
)
"""Its main parameter the track's resistance."""
