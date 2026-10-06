from .logic import Gate


class NOR(Gate):
    """Not or."""

    kind = "nor_gate"
    inputs_ = ("a", "b")
    terminals = (*inputs_, "y", "gnd")

    def logic(self, a, b):
        return (1 - a) * (1 - b)
