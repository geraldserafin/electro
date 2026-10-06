from ...element import Element


class Nullator(Element):
    """Neither a voltage nor a current: half of a nullor."""

    kind, prefix = "nullator", "N"
    terminals = ("a", "b")
    parameters = ()

    def laws(self, t, p):
        return [t.across("a", "b"), t.I["a"]]
