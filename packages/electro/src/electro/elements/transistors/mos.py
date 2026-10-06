"""A MOSFET (Shichman–Hodges, SPICE level 1, with the body diode and the gate's capacitances): a logic-level
power one unless given. A PMOS is an NMOS with every voltage and current the other way."""

import sympy as sp

from ...element import Element
from ...time import D
from ..physics import junction


def channel(p, ugs: sp.Expr, uds: sp.Expr) -> sp.Expr:
    """Drain to source through the channel, for ``uds`` ≥ 0: off below VTH, a resistor while ``uds`` is
    below the overdrive, a current source beyond."""
    ov = ugs - p["VTH"]
    clm = 1 + p["LAMBDA"] * uds
    return sp.Piecewise(
        (0, ov <= 0), (p["K"] * (ov * uds - uds**2 / 2) * clm, uds < ov), (p["K"] / 2 * ov**2 * clm, True)
    )


class MOS(Element):
    prefix = "Q"
    terminals = ("g", "d", "s")
    parameters = ("VTH", "K", "LAMBDA", "IS", "CGS", "CGD")
    defaults = {
        "VTH": 2,
        "K": sp.Rational(1, 2),
        "LAMBDA": sp.Rational(1, 100),
        "IS": sp.Rational(1, 10**14),
        "CGS": sp.Rational(1, 10**9),
        "CGD": sp.Rational(2, 10**10),
    }
    polarity = 1

    def laws(self, t, p):
        s = self.polarity
        ugs, uds = s * t.across("g", "s"), s * t.across("d", "s")
        ugd = ugs - uds
        through = sp.Piecewise((channel(p, ugs, uds), uds >= 0), (-channel(p, ugd, -uds), True))
        body = junction(-uds, p["IS"])
        cgs, cgd = p["CGS"] * D(ugs), p["CGD"] * D(ugd)
        return [t.I["d"] - s * (through - body - cgd), t.I["g"] - s * (cgs + cgd)]
