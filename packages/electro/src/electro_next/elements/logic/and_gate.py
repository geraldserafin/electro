from .logic import Gate


class AND(Gate):
    """And: high while both inputs are."""

    kind = "and_gate"
    inputs_ = ("a", "b")
    terminals = (*inputs_, "y", "gnd")

    def logic(self, a, b):
        return a * b
