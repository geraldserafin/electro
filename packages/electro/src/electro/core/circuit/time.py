"""The words a law uses for time. An analysis gives each its own meaning (``solver.analysis``)."""

from __future__ import annotations

import sympy as sp

D = sp.Function("D")
"""The derivative in time."""

Pre = sp.Function("Pre")
"""The value just before: memory."""

TIME = sp.Symbol("t")
"""Time, for data that change in it (a clock, a switch closed at 1 s)."""


def when(condition: sp.Basic, then: sp.Expr | float, otherwise: sp.Expr | float) -> sp.Expr:
    """``then`` while ``condition`` holds, else ``otherwise``."""
    return sp.Piecewise((then, condition), (otherwise, True))


def rising(x: sp.Expr, threshold: sp.Expr | float) -> sp.Basic:
    """``x`` crossing ``threshold`` upwards, now: above it, and not just before (an edge of a clock)."""
    return sp.And(x > threshold, Pre(x) <= threshold)


def square(high: sp.Expr | float, period: sp.Expr | float, low: sp.Expr | float = 0) -> sp.Expr:
    """A square wave in time: ``low`` the first half of each period, ``high`` the second."""
    return when(sp.Mod(TIME, period) < sp.Rational(1, 2) * period, low, high)
