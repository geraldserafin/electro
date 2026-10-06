from ..circuit.element import Element


class Resistor(Element):
    """U = R·I."""

    kind, prefix = "resistor", "R"
    terminals = ("a", "b")
    positive = ("",)

    def laws(self, t, p):
        return [t.across("a", "b") - p[""] * t.I["a"]]
