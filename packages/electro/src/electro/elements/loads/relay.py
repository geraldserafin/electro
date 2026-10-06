import sympy as sp

from ...circuit.element import Element
from ...circuit.time import D, Pre, when

R, L, R_LOSS = 70, sp.Rational(2, 100), 10_000
PULL, DROP = sp.Rational(5, 100), sp.Rational(15, 1000)
ON, OFF = 1000, sp.Rational(1, 10**10)


def contact(closed: sp.Expr) -> sp.Expr:
    return ON * closed + OFF * (1 - closed)


class Relay(Element):
    """A relay with a 5 V coil (an SRD-05VDC's: 70 Ω, 20 mH) between ``a`` and ``b``: it pulls in above
    ``PULL`` and lets go below ``DROP``, as it was just before (``I``: the coil's current, ``on``: whether it
    holds the contact). Its contact: ``com`` to ``nc`` at rest, to ``no`` pulled in."""

    kind, prefix = "relay", "K"
    terminals = ("a", "b", "com", "nc", "no")
    parameters = ()

    def laws(self, t, p):
        i, on = t.inner("I"), t.inner("on")
        u = t.across("a", "b")
        was = sp.Abs(Pre(i))
        no = contact(on) * t.across("com", "no")
        nc = contact(1 - on) * t.across("com", "nc")
        return [
            u - R * i - L * D(i),
            t.I["a"] - (i + u / R_LOSS),
            t.I["a"] + t.I["b"],
            on - when(was > PULL, 1, when(was < DROP, 0, Pre(on))),
            t.I["com"] - (no + nc),
            t.I["nc"] + nc,
        ]
