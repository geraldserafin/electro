import sympy as sp

from ...circuit.element import Element
from ..physics import junction


class Diode(Element):
    """Shockley's: ``a`` the anode, ``b`` the cathode; ``I_S``, ``n`` as its maker gives them."""

    kind, prefix = "diode", "D"
    terminals = ("a", "b")
    parameters = ("I_S", "n")
    defaults = {"I_S": sp.Rational(1, 10**14), "n": 1}

    def laws(self, t, p):
        return [t.I["a"] - junction(t.across("a", "b"), p["I_S"], p["n"])]
