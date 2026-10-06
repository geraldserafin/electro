import sympy as sp

from ...circuit.element import Element
from ...circuit.time import D

R, K, J, B = 5, sp.Rational(1, 100), sp.Rational(1, 10**6), sp.Rational(16, 10**7)


class Motor(Element):
    """A small DC motor (a 130-size one, 3–6 V): its winding and its back-EMF, K·ω; its rotor
    J·dω/dt = K·I − B·ω (``w``: ω, in rad/s)."""

    kind, prefix = "motor", "M"
    terminals = ("a", "b")
    parameters = ()

    def laws(self, t, p):
        w, i = t.inner("w"), t.I["a"]
        return [t.across("a", "b") - R * i - K * w, J * D(w) - (K * i - B * w)]
