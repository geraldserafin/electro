import sympy as sp

from ...circuit.element import Element
from ...circuit.time import when


class Switch(Element):
    """Closed (``closed`` 1): no voltage across it; open (0): no current through it. A hand sets it while
    it runs."""

    kind, prefix = "switch", "S"
    terminals = ("a", "b")
    parameters = ("closed",)
    defaults = {"closed": 0}
    inputs = ("closed",)

    def laws(self, t, p):
        return [when(p["closed"] > sp.Rational(1, 2), t.across("a", "b"), t.I["a"])]
