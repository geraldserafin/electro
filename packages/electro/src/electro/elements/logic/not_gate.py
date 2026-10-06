from .logic import Gate


class NOT(Gate):
    """Not: high while its input is low."""

    kind = "not_gate"
    inputs_ = ("a",)
    terminals = (*inputs_, "y", "gnd")

    def logic(self, a):
        return 1 - a
