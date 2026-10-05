"""Sources whose value changes in time: a sine, a square wave. Their ``+`` on their second end, as a
``VoltageSource``'s."""

from __future__ import annotations

import sympy as sp

from ..kind import Kind, Params, Terminals
from ..time import TIME, when


def _sine(t: Terminals, p: Params) -> list[sp.Expr]:
    """E·sin(2π·f·t + φ), φ in degrees. In AC it is the phasor E∠φ."""
    return [t.across("a", "b") + p[""] * sp.sin(2 * sp.pi * p["f"] * TIME + sp.pi * p["phase"] / 180)]


def _square(t: Terminals, p: Params) -> list[sp.Expr]:
    """E for the first ``duty`` of every period, then 0."""
    return [t.across("a", "b") + p[""] * when(sp.Mod(p["f"] * TIME, 1) < p["duty"], 1, 0)]


SineSource = Kind(
    "sine_source", "E", ("a", "b"), _sine, parameters=("", "f", "phase"), defaults=(("f", 50), ("phase", 0))
)
"""Its main parameter the amplitude, ``f`` the frequency (Hz), ``phase`` in degrees."""

SquareSource = Kind(
    "square_source",
    "E",
    ("a", "b"),
    _square,
    parameters=("", "f", "duty"),
    defaults=(("f", 1000), ("duty", sp.Rational(1, 2))),
)
"""A clock, a PWM signal: its main parameter the high level, ``f`` the frequency, ``duty`` the share high."""
