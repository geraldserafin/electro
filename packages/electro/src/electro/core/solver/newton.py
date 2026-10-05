"""Newton's method, for what algebra cannot solve (a diode's exp), made to arrive without any element's
own tricks. Two general ones only: the independent sources raised from nothing (``homotopy``), and a step
shortened while it does not bring the equations closer."""

from __future__ import annotations

from collections.abc import Callable, Sequence

import sympy as sp

from ..simulation.linear import solve_linear

Residual = Callable[..., Sequence[float]]
"""``(x, *extra)`` → each equation's value."""

Jacobian = Callable[..., Sequence[float]]
"""``(x, *extra)`` → the equations' derivatives, n × n, row by row."""

TOL = 1e-12


def compiled(
    exprs: Sequence[sp.Expr], unknowns: Sequence[sp.Symbol], extra: Sequence[sp.Symbol] = ()
) -> tuple[Residual, Jacobian]:
    """The equations and their Jacobian as plain functions of the unknowns (and ``extra``)."""
    n = len(unknowns)
    jacobian = sp.Matrix(list(exprs)).jacobian(list(unknowns))
    xs = sp.symbols(f"x0:{n}") if n else ()
    at = dict(zip(unknowns, xs))
    f = sp.lambdify([xs, *extra], [e.xreplace(at) for e in exprs], "math")
    j = sp.lambdify([xs, *extra], [jacobian[r, c].xreplace(at) for r in range(n) for c in range(n)], "math")
    return f, j


def newton(
    f: Residual, j: Jacobian, x0: Sequence[float], extra: Sequence[float] = (), max_iter: int = 100, damped: bool = True
) -> list[float] | None:
    """A root near ``x0``, or None. ``damped`` suits smooth laws. Across a jump (logic: 0 or 5, nothing
    between) a damped step stalls at the edge, so undamped takes whole steps till no branch changes."""
    x = list(x0)
    for _ in range(max_iter):
        jac = list(j(x, *extra))
        scale = _scales(jac, x)
        here = _distance(f, x, extra, scale)
        if here < TOL:
            return x
        dx = solve_linear(jac, [-v for v in f(x, *extra)], len(x))
        if dx is None:
            return None
        moved = _closer(f, x, dx, extra, scale, here) if damped else _moved(x, dx, 1.0)
        if moved is None:
            return None
        x = moved
        if _negligible(dx, x):
            return x
    return None


def homotopy(
    f: Residual, j: Jacobian, n: int, extra: Sequence[float] = (), x0: Sequence[float] | None = None
) -> list[float] | None:
    """A root of ``f(x, λ, *extra)`` at λ = 1, the sources raised from λ = 0, where everything is zero.
    Each raise starts where the last ended; a raise Newton does not finish is halved."""
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


def _scales(jac: Sequence[float], x: Sequence[float]) -> list[float]:
    """Each equation's scale: how much it moves when every unknown moves by its own size. Amperes and volts
    are not compared: 0.1 A on 10⁴ A is nearer than 10⁻⁴ V on 1 V."""
    n = len(x)
    return [max(sum(abs(jac[r * n + c]) * max(abs(x[c]), 1.0) for c in range(n)), 1e-300) for r in range(n)]


def _distance(f: Residual, x: Sequence[float], extra: Sequence[float], scale: Sequence[float]) -> float:
    """How far from a root, each equation against its scale. A step so far out that exp overflows is as
    far as it gets."""
    try:
        return max((abs(v) / s for v, s in zip(f(x, *extra), scale)), default=0.0)
    except (OverflowError, ValueError):
        return float("inf")


def _closer(
    f: Residual, x: list[float], dx: list[float], extra: Sequence[float], scale: Sequence[float], here: float
) -> list[float] | None:
    """The step, halved until it brings the equations closer; None when it never does."""
    t = 1.0
    while t > 1e-12:
        trial = _moved(x, dx, t)
        if _distance(f, trial, extra, scale) < here:
            return trial
        t /= 2
    return None


def _moved(x: Sequence[float], dx: Sequence[float], t: float) -> list[float]:
    return [a + t * d for a, d in zip(x, dx)]


def _negligible(dx: Sequence[float], x: Sequence[float]) -> bool:
    """Newton's own step is nothing: arrived. (A step shortened to nothing is not: that is stuck.)"""
    return max((abs(d) for d in dx), default=0.0) <= TOL * (1 + max((abs(a) for a in x), default=0.0))
