import sympy as sp

from ...circuit.element import Element

END = sp.Rational(1, 1000)
"""Its track never ends in a short circuit (ohms)."""


class Potentiometer(Element):
    """Its track (the main parameter) either side of the wiper ``w``, ``position`` of the way from ``a`` (0)
    to ``b`` (1)."""

    kind, prefix = "potentiometer", "P"
    terminals = ("a", "b", "w")
    parameters = ("", "position")
    defaults = {"position": sp.Rational(1, 2)}
    positive = ("",)
    inputs = ("position",)

    def laws(self, t, p):
        r, x = p[""], p["position"]
        return [
            t.across("a", "w") - (r * x + END) * t.I["a"],
            t.across("b", "w") - (r * (1 - x) + END) * t.I["b"],
        ]
