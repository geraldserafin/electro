import sympy as sp

from ...element import Element
from ...time import TIME, when


class SquareSource(Element):
    """A clock, a PWM signal: E for the first ``duty`` of every period of ``f``, then 0."""

    kind, prefix = "square_source", "E"
    terminals = ("a", "b")
    parameters = ("", "f", "duty")
    defaults = {"f": 1000, "duty": sp.Rational(1, 2)}

    def laws(self, t, p):
        return [t.across("a", "b") + p[""] * when(sp.Mod(p["f"] * TIME, 1) < p["duty"], 1, 0)]
