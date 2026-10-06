import sympy as sp

from ...algebra import Case, Cases
from ...element import Element


class DiodeDrop(Element):
    """The textbook's diode: on, at its forward drop U_F (the main parameter, 0.7 V unless given), any
    current in; or off, no current, below U_F."""

    kind, prefix = "diode_drop", "D"
    terminals = ("a", "b")
    defaults = {"": sp.Rational(7, 10)}

    def laws(self, t, p):
        u, i, drop = t.across("a", "b"), t.I["a"], p[""]
        return Cases((Case("on", (u - drop,), (i,)), Case("off", (i,), (drop - u,))))
