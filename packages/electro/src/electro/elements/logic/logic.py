"""Logic (74HC), powered at ``V_HIGH`` from its ``gnd`` (its supply pins not drawn, as logic diagrams have
it): inputs take no current and read 1 above half the supply; an output is a source of its level behind
``R_OUT``. A gate follows its inputs smoothly and a little late (so gates in a loop keep a state); a
flip-flop decides on its clock's rising edge, from what its inputs were just before it."""

import sympy as sp

from ...circuit.element import Element
from ...circuit.time import D, Pre, rising, when
from ..physics import high

V_HIGH = 5
R_OUT = 50
DELAY = sp.Rational(1, 10**7)
SHARP = 12
"""How sharply a gate's input turns from 0 to 1 around half the supply (1/V)."""
HALF = sp.Rational(V_HIGH, 2)


def level_before(t, terminal: str) -> sp.Expr:
    """An input as it was just before, read as 0 or 1."""
    return high(Pre(t.across(terminal, "gnd")), HALF)


def output(t, terminal: str, level: sp.Expr) -> sp.Expr:
    """The current into an output pin driven at ``level`` (0 to 1)."""
    return t.I[terminal] - (t.across(terminal, "gnd") - V_HIGH * level) / R_OUT


def clocked(t) -> sp.Basic:
    """The clock's rising edge, now."""
    return rising(t.across("clk", "gnd"), HALF)


class Gate(Element):
    """A gate of ``inputs``, its output ``y`` what ``logic`` makes of them (each from 0 to 1)."""

    prefix = "U"
    parameters = ()
    ground = True
    inputs_: tuple[str, ...] = ()

    def logic(self, *levels: sp.Expr) -> sp.Expr:
        raise NotImplementedError

    def laws(self, t, p):
        y = t.inner("y")
        soft = [1 / (1 + sp.exp(-SHARP * (t.across(i, "gnd") - HALF))) for i in self.inputs_]
        return [
            *(t.I[i] for i in self.inputs_),
            DELAY * D(y) - (V_HIGH * self.logic(*soft) - y),
            t.I["y"] - (t.across("y", "gnd") - y) / R_OUT,
        ]


class FlipFlop(Element):
    """On a rising edge its state becomes what ``following`` makes of the state and its ``inputs_``' levels
    just before it; ``q`` and ``nq`` show it."""

    prefix = "U"
    parameters = ()
    ground = True
    inputs_: tuple[str, ...] = ()

    def following(self, q: sp.Expr, *levels: sp.Expr) -> sp.Expr:
        raise NotImplementedError

    def laws(self, t, p):
        q = t.inner("q")
        after = self.following(Pre(q), *(level_before(t, i) for i in self.inputs_))
        return [
            *(t.I[i] for i in (*self.inputs_, "clk")),
            q - when(clocked(t), after, Pre(q)),
            output(t, "q", q),
            output(t, "nq", 1 - q),
        ]
