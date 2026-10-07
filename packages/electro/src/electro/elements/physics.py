"""What several kinds' laws share: a p-n junction, a logic level."""

import sympy as sp

from ..time import when

V_T = sp.Rational(25852, 1000000)
"""The thermal voltage at 300 K."""


class pn(sp.Function):
    """e^x of a p-n junction, ``x`` = (u − u₀)/(n·V_T), passing ``i`` at u₀ (times e^x): an exponential that
    knows it is a junction's, so that Newton approaches it along its bend, as SPICE does (``code``)."""

    nargs = 3

    @classmethod
    def eval(cls, x, i_s, nvt):
        if x.is_number:
            return sp.exp(x)

    def fdiff(self, argindex=1):
        return self if argindex == 1 else sp.S.Zero

    def _eval_rewrite_as_exp(self, x, i_s, nvt, **kwargs):
        return sp.exp(x)

    def _sympystr(self, printer):
        return printer._print(sp.exp(self.args[0]))

    def _latex(self, printer, exp=None):
        return printer._print(sp.exp(self.args[0]))


def junction(u: sp.Expr, i_s: sp.Expr, n: sp.Expr | float = 1) -> sp.Expr:
    """Shockley's: the current a p-n junction passes at ``u``, I_S·(e^(u/(n·V_T)) − 1)."""
    nvt = n * V_T
    return i_s * (pn(u / nvt, i_s, nvt) - 1)


def high(u: sp.Expr, threshold: sp.Expr | float) -> sp.Expr:
    """1 above ``threshold``, else 0."""
    return when(u > threshold, 1, 0)
