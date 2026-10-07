import sympy as sp

from ...element import Element
from ..physics import V_T, junction, pn

I_S, I_ZT = sp.Rational(1, 10**14), sp.Rational(5, 1000)


class Zener(Element):
    """Forward a diode; backwards it breaks down at its main parameter U_Z: I_ZT flows at U = −U_Z, and every
    V_T further multiplies it by e. Nothing flows with nothing across it."""

    kind, prefix = "zener", "DZ"
    terminals = ("a", "b")

    def laws(self, t, p):
        u = t.across("a", "b")
        breakdown = I_ZT * (pn((-u - p[""]) / V_T, I_ZT, V_T) - sp.exp(-p[""] / V_T))
        return [t.I["a"] - (junction(u, I_S) - breakdown)]
