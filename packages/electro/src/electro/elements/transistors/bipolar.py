"""A bipolar transistor (Ebers–Moll, with its junctions' capacitances). A PNP is an NPN with every voltage and
current the other way."""

import sympy as sp

from ...element import Element
from ...time import D
from ..physics import junction


class Bipolar(Element):
    prefix = "Q"
    terminals = ("b", "c", "e")
    parameters = ("IS", "BF", "BR", "CJE", "CJC")
    defaults = {
        "IS": sp.Rational(1, 10**14),
        "BF": 100,
        "BR": 1,
        "CJE": sp.Rational(8, 10**12),
        "CJC": sp.Rational(4, 10**12),
    }
    polarity = 1

    def laws(self, t, p):
        s = self.polarity
        ube, ubc = s * t.across("b", "e"), s * t.across("b", "c")
        i_s = p["IS"]
        forward, reverse = junction(ube, i_s) / i_s, junction(ubc, i_s) / i_s
        cbe, cbc = p["CJE"] * D(ube), p["CJC"] * D(ubc)
        collector = i_s * (forward - reverse) - i_s / p["BR"] * reverse - cbc
        base = i_s / p["BF"] * forward + i_s / p["BR"] * reverse + cbe + cbc
        return [t.I["c"] - s * collector, t.I["b"] - s * base]
