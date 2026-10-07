"""What several kinds' laws share: a p-n junction, a logic level."""

import sympy as sp

from ..time import when

V_T = sp.Rational(25852, 1000000)
"""The thermal voltage at 300 K."""


def junction(u: sp.Expr, i_s: sp.Expr, n: sp.Expr | float = 1) -> sp.Expr:
    """Shockley's: the current a p-n junction passes at ``u``, I_S·(e^(u/(n·V_T)) − 1)."""
    return i_s * (sp.exp(u / (n * V_T)) - 1)


def high(u: sp.Expr, threshold: sp.Expr | float) -> sp.Expr:
    """1 above ``threshold``, else 0."""
    return when(u > threshold, 1, 0)
