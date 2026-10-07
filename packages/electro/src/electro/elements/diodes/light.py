"""An LED's current, its forward voltage given at the current it is lit fully by."""

import sympy as sp

from ..physics import V_T, pn

LED_N = 2
LED_RATED = sp.Rational(2, 100)


def led(u: sp.Expr, forward: sp.Expr | float) -> sp.Expr:
    """The current through an LED of ``forward`` volts at ``LED_RATED``: nothing at 0 V."""
    nvt = LED_N * V_T
    return LED_RATED * (pn((u - forward) / nvt, LED_RATED, nvt) - sp.exp(-forward / nvt))
