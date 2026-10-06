import sympy as sp

from ...element import Element

GAMMA = sp.Rational(7, 10)


class Photoresistor(Element):
    """R·(E/10 lx)^−γ, γ a GL5528's: its main parameter its resistance at 10 lux; ``lux`` the light on it
    (100: a room), set by the world while it runs."""

    kind, prefix = "photoresistor", "LDR"
    terminals = ("a", "b")
    parameters = ("", "lux")
    defaults = {"lux": 100}
    positive = ("",)
    inputs = ("lux",)

    def laws(self, t, p):
        return [t.across("a", "b") - p[""] * (p["lux"] / 10) ** -GAMMA * t.I["a"]]
