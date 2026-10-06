import sympy as sp

from ...circuit.element import Element
from .light import led

FORWARD = {"r": 2, "g": 3, "b": sp.Rational(31, 10)}


class RGBLED(Element):
    """Red, green and blue in one, a common cathode ``k``."""

    kind, prefix = "rgb_led", "LED"
    terminals = ("r", "g", "b", "k")
    parameters = ()

    def laws(self, t, p):
        return [t.I[pin] - led(t.across(pin, "k"), f) for pin, f in FORWARD.items()]
