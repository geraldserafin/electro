"""``exp`` for a simulation: beyond ``EXP_LIMIT`` it grows along its tangent, so Newton's first guesses never
overflow. Printed for Python and JavaScript as functions of their own (the page's engine has them)."""

from __future__ import annotations

import math

import sympy as sp

EXP_LIMIT = 80.0


def limited_exp(x: float) -> float:
    return math.exp(x) if x <= EXP_LIMIT else math.exp(EXP_LIMIT) * (1 + x - EXP_LIMIT)


def limited_exp_slope(x: float) -> float:
    return math.exp(min(x, EXP_LIMIT))


class limexp(sp.Function):
    """``exp(x)``, continued by its tangent beyond ``EXP_LIMIT``."""

    def fdiff(self, argindex=1):
        return dlimexp(self.args[0])

    def _pythoncode(self, printer):
        return f"limexp({printer._print(self.args[0])})"

    def _javascript(self, printer):
        return f"limexp({printer._print(self.args[0])})"


class dlimexp(sp.Function):
    """``limexp``'s derivative."""

    def _pythoncode(self, printer):
        return f"dlimexp({printer._print(self.args[0])})"

    def _javascript(self, printer):
        return f"dlimexp({printer._print(self.args[0])})"
