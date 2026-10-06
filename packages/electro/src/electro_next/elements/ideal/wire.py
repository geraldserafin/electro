from ...element import Element


class Wire(Element):
    """A wire: no voltage across it."""

    kind, prefix = "wire", "W"
    terminals = ("a", "b")
    parameters = ()

    def laws(self, t, p):
        return [t.across("a", "b")]
