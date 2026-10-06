"""Ideal elements: a wire, a break, the nullor's halves, an unknown, meters, an op-amp."""

from __future__ import annotations

import sympy as sp

from ..kind import Kind, Params, Terminals


def _same_potential(t: Terminals, _: Params) -> list[sp.Expr]:
    return [t.across("a", "b")]


def _no_current(t: Terminals, _: Params) -> list[sp.Expr]:
    return [t.I["a"]]


def _anything(t: Terminals, _: Params) -> list[sp.Expr]:
    return []


def _nothing_through(t: Terminals, p: Params) -> list[sp.Expr]:
    """Neither a drop nor a current."""
    return _same_potential(t, p) + _no_current(t, p)


def _op_amp(t: Terminals, _: Params) -> list[sp.Expr]:
    """Its inputs at one potential, taking nothing; its output whatever it takes, returned through its
    supply (gnd): charge is kept, so the current out of a real one comes back somewhere."""
    return [t.across("plus", "minus"), t.I["plus"], t.I["minus"]]


Wire = Kind("wire", "W", ("a", "b"), _same_potential, parameters=())
Open = Kind("open", "O", ("a", "b"), _no_current, parameters=())
Nullator = Kind("nullator", "N", ("a", "b"), _nothing_through, parameters=())
Norator = Kind("norator", "O", ("a", "b"), _anything, parameters=())
Hole = Kind("hole", "X", ("a", "b"), _anything, parameters=())
"""An element not known: anything at all. ``methods.fill`` finds the simplest that fits."""
Ammeter = Kind("ammeter", "A", ("a", "b"), _same_potential, parameters=())
"""A wire whose current is what is read."""
Voltmeter = Kind("voltmeter", "V", ("a", "b"), _no_current, parameters=())
"""A break whose voltage is what is read."""
OpAmp = Kind("opamp", "OA", ("plus", "minus", "out", "gnd"), _op_amp, parameters=(), ground=True)
"""Ideal, with negative feedback. ``gnd``: its supply's return, not drawn on a schematic."""
