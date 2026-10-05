"""Logic: inputs take no current, an output is a source of its level (``V_HIGH`` or 0 against gnd)."""

from __future__ import annotations

import sympy as sp

from ..kind import Kind, Params, Terminals
from ..time import Pre, rising, when

V_HIGH = 5


def _not(t: Terminals, _: Params) -> list[sp.Expr]:
    return [t.I["in"], t.V["out"] - t.V["gnd"] - when(_level(t, "in"), 0, V_HIGH)]


def _flip_flop(t: Terminals, _: Params) -> list[sp.Expr]:
    """On the clock's rising edge it takes what was on d the instant before (so a loop from q back to d
    never asks for its own answer), and holds it in ``s`` till the next edge."""
    s = t.inner("s")
    clk, d = t.V["clk"] - t.V["gnd"], t.V["d"] - t.V["gnd"]
    edge = rising(clk, V_HIGH / 2)
    return [
        t.I["d"],
        t.I["clk"],
        t.V["q"] - t.V["gnd"] - V_HIGH * s,
        s - when(edge, when(Pre(d) > V_HIGH / 2, 1, 0), Pre(s)),
    ]


def _level(t: Terminals, terminal: str) -> sp.Basic:
    """High: above half of ``V_HIGH``."""
    return t.V[terminal] - t.V["gnd"] > V_HIGH / 2


Not = Kind("not_gate", "U", ("in", "out", "gnd"), _not, parameters=())
DFlipFlop = Kind("d_flip_flop", "FF", ("d", "clk", "q", "gnd"), _flip_flop, parameters=())
