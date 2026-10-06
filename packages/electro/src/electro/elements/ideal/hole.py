from ...circuit.element import Element


class Hole(Element):
    """An element not known, anything at all: the notebook's ``fill`` finds the simplest that fits."""

    kind, prefix = "hole", "X"
    terminals = ("a", "b")
    parameters = ()

    def laws(self, t, p):
        return []
