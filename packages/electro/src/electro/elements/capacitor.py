from ..element import Element
from ..time import D


class Capacitor(Element):
    """I = C·dU/dt."""

    kind, prefix = "capacitor", "C"
    terminals = ("a", "b")
    positive = ("",)

    def laws(self, t, p):
        return [t.I["a"] - p[""] * D(t.across("a", "b"))]
