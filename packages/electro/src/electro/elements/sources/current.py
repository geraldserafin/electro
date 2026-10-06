from ...circuit.element import Element


class CurrentSource(Element):
    """It pushes J from its first end to its second."""

    kind, prefix = "current_source", "J"
    terminals = ("a", "b")

    def laws(self, t, p):
        return [t.I["a"] - p[""]]
