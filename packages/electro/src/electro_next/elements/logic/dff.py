from .logic import FlipFlop


class DFlipFlop(FlipFlop):
    """On a rising edge q takes d (a half of a 74HC74)."""

    kind = "dff"
    inputs_ = ("d",)
    terminals = ("d", "clk", "q", "nq", "gnd")

    def following(self, q, d):
        return d
