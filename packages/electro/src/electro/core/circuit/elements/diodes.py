"""Diodes: Shockley's, the textbook's two straight pieces of it, a Zener, LEDs (one, three in one, a
seven-segment digit)."""

from __future__ import annotations

from collections.abc import Mapping

import sympy as sp

from ..kind import Case, Cases, Kind, Params, Terminals
from .physics import V_T, junction

LED_N = 2
LED_RATED = sp.Rational(2, 100)
"""An LED's current at full brightness (A): its forward voltage is given at it."""

LED_COLORS = {"red": 2, "orange": 2.05, "yellow": 2.1, "green": 2.2, "blue": 3.1, "white": 3.2}
"""An LED's forward voltage at ``LED_RATED`` by its colour."""

DIODE_PARTS = {"1N4148": {"I_S": 2.52e-9, "n": 1.752}, "1N4007": {"I_S": 76.9e-12, "n": 1.45}}
"""Real diodes' parameters, as their makers' SPICE models have them."""

ZENER_I_S, ZENER_I_ZT = sp.Rational(1, 10**14), sp.Rational(5, 1000)


def _shockley(t: Terminals, p: Params) -> list[sp.Expr]:
    return [t.I["a"] - junction(t.across("a", "b"), p["I_S"], p["n"])]


def _on_or_off(t: Terminals, p: Params) -> Cases:
    """On: at its forward drop U_F, any current in. Off: no current, below U_F."""
    u, i, drop = t.across("a", "b"), t.I["a"], p[""]
    return Cases((Case("on", (u - drop,), (i,)), Case("off", (i,), (drop - u,))))


def led(u: sp.Expr, forward: sp.Expr | float) -> sp.Expr:
    """The current through an LED of ``forward`` volts at ``LED_RATED``."""
    nvt = LED_N * V_T
    return LED_RATED * (sp.exp((u - forward) / nvt) - sp.exp(-forward / nvt))


def _led(t: Terminals, p: Params) -> list[sp.Expr]:
    return [t.I["a"] - led(t.across("a", "b"), p[""])]


def _zener(t: Terminals, p: Params) -> list[sp.Expr]:
    """Forward a diode; backwards it breaks down: I_ZT flows at U = −U_Z, and every V_T further multiplies
    it by e."""
    u = t.across("a", "b")
    breakdown = ZENER_I_ZT * sp.exp((-u - p[""]) / V_T)
    return [t.I["a"] - (junction(u, ZENER_I_S) - breakdown)]


def _leds(forward: Mapping[str, sp.Expr | float], common: str):
    """LEDs from each of ``forward``'s terminals to one ``common`` cathode."""

    def laws(t: Terminals, _: Params) -> list[sp.Expr]:
        return [t.I[pin] - led(t.across(pin, common), f) for pin, f in forward.items()]

    return laws


RGB = {"r": 2, "g": 3, "b": sp.Rational(31, 10)}
SEGMENTS = ("a", "b", "c", "d", "e", "f", "g", "dp")

Diode = Kind(
    "diode", "D", ("a", "b"), _shockley, parameters=("I_S", "n"), defaults=(("I_S", sp.Rational(1, 10**14)), ("n", 1))
)
"""``a`` the anode, ``b`` the cathode."""

DiodeDrop = Kind("diode_drop", "D", ("a", "b"), _on_or_off, defaults=(("", sp.Rational(7, 10)),))
"""The textbook's diode: its main parameter is its forward drop U_F, 0.7 V unless given."""

LED = Kind("led", "LED", ("a", "b"), _led, defaults=(("", 2),))
"""Its main parameter its forward voltage at 20 mA (``LED_COLORS``: red unless given)."""

Zener = Kind("zener", "DZ", ("a", "b"), _zener)
"""Its main parameter its breakdown voltage U_Z."""

RGBLED = Kind("rgb_led", "LED", ("r", "g", "b", "k"), _leds(RGB, "k"), parameters=())
"""Red, green and blue in one, a common cathode ``k``."""

SevenSegment = Kind("seven_segment", "DS", (*SEGMENTS, "com"), _leds(dict.fromkeys(SEGMENTS, 2), "com"), parameters=())
"""A digit (a 5161AS): red segments ``a``–``g`` and the dot ``dp``, a common cathode ``com``."""
