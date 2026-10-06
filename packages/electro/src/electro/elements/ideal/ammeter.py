from ...element import Element


class Ammeter(Element):
    """A wire whose current is what is read."""

    kind, prefix = "ammeter", "A"
    terminals = ("a", "b")
    parameters = ()

    def laws(self, t, p):
        return [t.across("a", "b")]
