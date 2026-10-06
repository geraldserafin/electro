from ...circuit.element import Element
from ...circuit.time import Pre, when
from ..physics import high
from .logic import HALF, clocked, output


class Counter(Element):
    """A 4-bit synchronous binary counter (a 74HC161 without its load and enable): one up on each rising edge
    of ``clk`` (``q0`` the lowest bit), 15 then 0; ``reset`` high holds it at 0. ``count``: the number it
    holds."""

    kind, prefix = "counter", "U"
    terminals = ("clk", "reset", "q0", "q1", "q2", "q3", "gnd")
    parameters = ()
    ground = True

    def laws(self, t, p):
        bits = [t.inner(f"q{k}") for k in range(4)]
        keep = 1 - high(t.across("reset", "gnd"), HALF)
        carry = when(clocked(t), 1, 0)
        laws = [t.I["clk"], t.I["reset"]]
        for k, b in enumerate(bits):
            was = Pre(b)
            laws += [b - keep * (was + carry - 2 * was * carry), output(t, f"q{k}", b)]
            carry = carry * was
        laws.append(t.inner("count") - sum(b * 2**k for k, b in enumerate(bits)))
        return laws
