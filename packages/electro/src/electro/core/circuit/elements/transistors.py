"""Transistors: bipolar (Ebers–Moll, with its junctions' capacitances) and MOSFETs (Shichman–Hodges,
SPICE level 1, with the body diode and the gate's capacitances). A PNP and a PMOS are an NPN and an NMOS
with every voltage and current the other way."""

from __future__ import annotations

import sympy as sp

from ..kind import Kind, Params, Terminals
from ..time import D
from .physics import V_T, junction

BJT_PARTS = {
    "BC547B": {"IS": 2.39e-14, "BF": 294.3, "BR": 7.946},
    "2N2222": {"IS": 14.34e-15, "BF": 255.9, "BR": 6.092},
    "2N3904": {"IS": 6.734e-15, "BF": 416.4, "BR": 0.7371},
    "BC557B": {"IS": 3.83e-14, "BF": 344.4, "BR": 14.84},
    "2N3906": {"IS": 1.41e-15, "BF": 180.7, "BR": 4.977},
}
"""Real transistors' parameters, as their makers' SPICE models have them."""

BJT_DEFAULTS = (
    ("IS", sp.Rational(1, 10**14)),
    ("BF", 100),
    ("BR", 1),
    ("CJE", sp.Rational(8, 10**12)),
    ("CJC", sp.Rational(4, 10**12)),
)
MOS_DEFAULTS = (
    ("VTH", 2),
    ("K", sp.Rational(1, 2)),
    ("LAMBDA", sp.Rational(1, 100)),
    ("IS", sp.Rational(1, 10**14)),
    ("CGS", sp.Rational(1, 10**9)),
    ("CGD", sp.Rational(2, 10**10)),
)
"""A logic-level power MOSFET's."""


def _bipolar(polarity: int):
    def laws(t: Terminals, p: Params) -> list[sp.Expr]:
        ube, ubc = polarity * t.across("b", "e"), polarity * t.across("b", "c")
        forward, reverse = sp.exp(ube / V_T) - 1, sp.exp(ubc / V_T) - 1
        cbe, cbc = p["CJE"] * D(ube), p["CJC"] * D(ubc)
        i_s = p["IS"]
        collector = i_s * (forward - reverse) - i_s / p["BR"] * reverse - cbc
        base = i_s / p["BF"] * forward + i_s / p["BR"] * reverse + cbe + cbc
        return [t.I["c"] - polarity * collector, t.I["b"] - polarity * base]

    return laws


def _channel(p: Params, ugs: sp.Expr, uds: sp.Expr) -> sp.Expr:
    """Drain to source through the channel, for ``uds`` ≥ 0: off below VTH, a resistor while ``uds`` is
    below the overdrive, a current source beyond."""
    ov = ugs - p["VTH"]
    clm = 1 + p["LAMBDA"] * uds
    return sp.Piecewise(
        (0, ov <= 0),
        (p["K"] * (ov * uds - uds**2 / 2) * clm, uds < ov),
        (p["K"] / 2 * ov**2 * clm, True),
    )


def _mos(polarity: int):
    def laws(t: Terminals, p: Params) -> list[sp.Expr]:
        ugs, uds = polarity * t.across("g", "s"), polarity * t.across("d", "s")
        ugd = ugs - uds
        channel = sp.Piecewise((_channel(p, ugs, uds), uds >= 0), (-_channel(p, ugd, -uds), True))
        body = junction(-uds, p["IS"])
        cgs, cgd = p["CGS"] * D(ugs), p["CGD"] * D(ugd)
        return [t.I["d"] - polarity * (channel - body - cgd), t.I["g"] - polarity * (cgs + cgd)]

    return laws


def _bjt(name: str, polarity: int) -> Kind:
    return Kind(
        name,
        "Q",
        ("b", "c", "e"),
        _bipolar(polarity),
        parameters=tuple(k for k, _ in BJT_DEFAULTS),
        defaults=BJT_DEFAULTS,
    )


def _mosfet(name: str, polarity: int) -> Kind:
    return Kind(
        name, "Q", ("g", "d", "s"), _mos(polarity), parameters=tuple(k for k, _ in MOS_DEFAULTS), defaults=MOS_DEFAULTS
    )


NPN = _bjt("npn", 1)
PNP = _bjt("pnp", -1)
NMOS = _mosfet("nmos", 1)
PMOS = _mosfet("pmos", -1)
