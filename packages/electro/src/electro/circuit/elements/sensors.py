"""Resistors that sense: their resistance a function of what they sense, set by the world while it runs."""

from __future__ import annotations

import sympy as sp

from ..kind import Kind, Params, Terminals

LDR_GAMMA = sp.Rational(7, 10)
THERMISTOR_B, KELVIN = 3950, sp.Rational(27315, 100)


def _photoresistor(t: Terminals, p: Params) -> list[sp.Expr]:
    """R·(E/10 lx)^−γ, γ a GL5528's."""
    return [t.across("a", "b") - p[""] * (p["lux"] / 10) ** -LDR_GAMMA * t.I["a"]]


def _thermistor(t: Terminals, p: Params) -> list[sp.Expr]:
    """An NTC's: R·e^(B·(1/T − 1/T₂₅))."""
    factor = sp.exp(THERMISTOR_B * (1 / (p["temperature"] + KELVIN) - 1 / (25 + KELVIN)))
    return [t.across("a", "b") - p[""] * factor * t.I["a"]]


Photoresistor = Kind(
    "photoresistor",
    "LDR",
    ("a", "b"),
    _photoresistor,
    parameters=("", "lux"),
    defaults=(("lux", 100),),
    positive=("",),
    inputs=("lux",),
)
"""Its main parameter its resistance at 10 lux; ``lux`` the light on it (100: a room)."""

Thermistor = Kind(
    "thermistor",
    "RT",
    ("a", "b"),
    _thermistor,
    parameters=("", "temperature"),
    defaults=(("temperature", 25),),
    positive=("",),
    inputs=("temperature",),
)
"""Its main parameter its resistance at 25 °C; ``temperature`` in °C."""
