from .logic import Gate


class OR(Gate):
    """Or: high while either input is."""

    kind = "or_gate"
    inputs_ = ("a", "b")
    terminals = (*inputs_, "y", "gnd")

    def logic(self, a, b):
        return 1 - (1 - a) * (1 - b)
