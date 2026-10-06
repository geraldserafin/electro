from ...element import Element


class OpAmp(Element):
    """Ideal, with negative feedback: its inputs at one potential, taking nothing; its output whatever it
    takes, returned through its supply (``gnd``, not drawn): charge is kept."""

    kind, prefix = "opamp", "OA"
    terminals = ("plus", "minus", "out", "gnd")
    parameters = ()
    ground = True

    def laws(self, t, p):
        return [t.across("plus", "minus"), t.I["plus"], t.I["minus"]]
