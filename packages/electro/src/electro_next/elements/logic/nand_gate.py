from .logic import Gate


class NAND(Gate):
    """Not and."""

    kind = "nand_gate"
    inputs_ = ("a", "b")
    terminals = (*inputs_, "y", "gnd")

    def logic(self, a, b):
        return 1 - a * b
