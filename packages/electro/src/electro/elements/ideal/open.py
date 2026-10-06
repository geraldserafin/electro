from ...circuit.element import Element


class Open(Element):
    """A break: no current through it."""

    kind, prefix = "open", "O"
    terminals = ("a", "b")
    parameters = ()

    def laws(self, t, p):
        return [t.I["a"]]
