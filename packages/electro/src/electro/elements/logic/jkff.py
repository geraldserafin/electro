from .logic import FlipFlop


class JKFlipFlop(FlipFlop):
    """On a rising edge j sets, k resets, both toggle, neither holds."""

    kind = "jkff"
    inputs_ = ("j", "k")
    terminals = ("j", "clk", "k", "q", "nq", "gnd")

    def following(self, q, j, k):
        return j * (1 - q) + (1 - k) * q
