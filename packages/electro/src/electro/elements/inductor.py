from ..circuit.element import Element
from ..circuit.time import D


class Inductor(Element):
    """U = L·dI/dt."""

    kind, prefix = "inductor", "L"
    terminals = ("a", "b")
    positive = ("",)

    def laws(self, t, p):
        return [t.across("a", "b") - p[""] * D(t.I["a"])]
