from ...circuit.element import Element


class Norator(Element):
    """Anything at all: the other half of a nullor."""

    kind, prefix = "norator", "O"
    terminals = ("a", "b")
    parameters = ()

    def laws(self, t, p):
        return []
