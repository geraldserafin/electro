from .logic import Gate


class XOR(Gate):
    """Exclusive or: high while one input is, not both."""

    kind = "xor_gate"
    inputs_ = ("a", "b")
    terminals = (*inputs_, "y", "gnd")

    def logic(self, a, b):
        return a + b - 2 * a * b
