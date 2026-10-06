from ...element import Element


class Voltmeter(Element):
    """A break whose voltage is what is read."""

    kind, prefix = "voltmeter", "V"
    terminals = ("a", "b")
    parameters = ()

    def laws(self, t, p):
        return [t.I["a"]]
