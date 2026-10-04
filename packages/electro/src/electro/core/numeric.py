"""Solving what algebra cannot (a diode's exp): Newton's method, made to arrive without any element's own
tricks. Two general ones only: the independent sources raised from nothing (``homotopy`` — with them off
every quantity is zero, and each raise starts where the last ended), and a step shortened while it does
not bring the equations closer (or runs out of numbers). Which elements are sources is read off their laws.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

import sympy as sp

from electro.sim import _solve_linear

Residual = Callable[..., Sequence[float]]  # (x, *extra) -> each equation's value
Jacobian = Callable[..., Sequence[float]]  # (x, *extra) -> its derivatives, n × n row by row

TOL = 1e-12


def compiled(
    exprs: Sequence[sp.Expr], unknowns: Sequence[sp.Symbol], extra: Sequence[sp.Symbol] = ()
) -> tuple[Residual, Jacobian]:
    """The equations and their Jacobian as plain functions of the unknowns (and ``extra``)."""
    n = len(unknowns)
    jacobian = sp.Matrix(list(exprs)).jacobian(list(unknowns))
    xs = sp.symbols(f"x0:{n}") if n else ()
    at = dict(zip(unknowns, xs, strict=True))
    f = sp.lambdify([xs, *extra], [e.xreplace(at) for e in exprs], "math")
    j = sp.lambdify([xs, *extra], [jacobian[r, c].xreplace(at) for r in range(n) for c in range(n)], "math")
    return f, j


def _relative(f: Residual, x: Sequence[float], extra: Sequence[float], scale: Sequence[float]) -> float:
    """How far from a root: each equation's value against its own scale (amperes and volts are not
    compared — 0.1 A on 10⁴ A is nearer than 10⁻⁴ V on 1 V)."""
    try:
        return max((abs(v) / s for v, s in zip(f(x, *extra), scale, strict=True)), default=0.0)
    except (OverflowError, ValueError):  # (a step so far out that exp overflows: as bad as it gets)
        return float("inf")


def newton(
    f: Residual, j: Jacobian, x0: Sequence[float], extra: Sequence[float] = (), max_iter: int = 100
) -> list[float] | None:
    """A root near ``x0``; None: not reached."""
    x = list(x0)
    n = len(x)
    for _ in range(max_iter):
        jac = list(j(x, *extra))
        # each equation's scale: how much it moves when every unknown moves by its own size
        scale = [max(sum(abs(jac[r * n + c]) * max(abs(x[c]), 1.0) for c in range(n)), 1e-300) for r in range(n)]
        here = _relative(f, x, extra, scale)
        if here < TOL:
            return x
        dx = _solve_linear(jac, [-v for v in f(x, *extra)], n)
        if dx is None:
            return None
        t = 1.0
        while t > 1e-12:  # (shorter, while it does not bring the equations closer)
            trial = [a + t * d for a, d in zip(x, dx, strict=True)]
            if _relative(f, trial, extra, scale) < here:
                break
            t /= 2
        else:
            return None
        x = trial
        if max((abs(t * d) for d in dx), default=0.0) <= TOL * (1 + max(abs(a) for a in x)):
            return x
    return None


def homotopy(
    f: Residual, j: Jacobian, n: int, extra: Sequence[float] = (), x0: Sequence[float] | None = None
) -> list[float] | None:
    """A root of ``f(x, λ, *extra)`` at λ = 1, the sources raised from λ = 0 (nothing on: every quantity
    zero) — each raise from where the last ended, a raise halved while Newton does not get there."""
    x = newton(f, j, list(x0) if x0 is not None else [0.0] * n, (0.0, *extra))
    lam, raise_by = 0.0, 0.25
    while x is not None and lam < 1:
        to = min(1.0, lam + raise_by)
        found = newton(f, j, x, (to, *extra))
        if found is None:
            raise_by /= 2
            if raise_by < 1e-6:
                return None
            continue
        x, lam, raise_by = found, to, min(1.0, raise_by * 2)
    return x
