"""Solving as one does by hand: an equation with one unknown left at a time, its origin the reason; when
no such equation is left, the rest together."""

from __future__ import annotations

import sympy as sp

from .algebra import Equation, SolutionStep, expr, subs, symbols_in
from .errors import Ambiguous, Contradiction
from .formula import System

Known = dict[sp.Symbol, sp.Expr]


def solve_by_hand(system: System) -> tuple[Known, tuple[SolutionStep, ...]]:
    known: Known = {}
    steps: list[SolutionStep] = []
    pending = list(system.equations)
    while pending := _unsettled(pending, known, system):
        alone = _alone(pending, known, system)
        if alone is None:
            together = _together(pending, known, system)
            known |= together
            origins = tuple(eq.origin for eq in pending)
            exprs = tuple(eq.expr for eq in pending)
            steps.append(SolutionStep(tuple(together), tuple(together.values()), origins, "together", exprs))
            break
        eq, x, value = alone
        pending.remove(eq)
        known[x] = value
        steps.append(SolutionStep((x,), (value,), (eq.origin,), equations=(eq.expr,)))
    return known, tuple(steps)


def _unsettled(pending: list[Equation], known: Known, system: System) -> list[Equation]:
    """The equations with an unknown still in them. One with none left must hold, or the data
    contradict each other."""
    unsettled = []
    for eq in pending:
        e = subs(eq.expr, known)
        if symbols_in(e) & set(system.unknowns):
            unsettled.append(eq)
        elif sp.simplify(e) != 0:
            raise Contradiction(f"no solution: the data contradict each other ({eq.origin.what})")
    return unsettled


def _alone(pending: list[Equation], known: Known, system: System) -> tuple[Equation, sp.Symbol, sp.Expr] | None:
    """The first equation with one unknown left and one value for it. Two values (a resistance from its
    power) wait for the rest."""
    for eq in pending:
        e = subs(eq.expr, known)
        left = symbols_in(e) & set(system.unknowns)
        if len(left) != 1:
            continue
        (x,) = left
        roots = [r for r in sp.solve(e, x) if _fits(x, r, system)]
        if not roots:
            raise Contradiction(f"no solution: the data contradict each other ({eq.origin.what})")
        if len(roots) == 1:
            return eq, x, sp.simplify(roots[0])
    return None


def _together(pending: list[Equation], known: Known, system: System) -> Known:
    exprs = [subs(eq.expr, known) for eq in pending]
    rest = sorted({x for e in exprs for x in symbols_in(e)} & set(system.unknowns), key=str)
    options = [f for f in sp.solve(exprs, rest, dict=True) if all(_fits(x, v, system) for x, v in f.items())]
    if not options:
        raise Contradiction("no solution: the data contradict each other")
    if len(options) > 1:
        raise Ambiguous([{x: sp.simplify(v) for x, v in f.items() if x in system.params} for f in options])
    return {x: sp.simplify(v) for x, v in options[0].items()}


def _fits(x: sp.Symbol, value: object, system: System) -> bool:
    """Not a negative value of what is never negative: a resistance of −34 Ω is no circuit."""
    v = expr(value)
    return x not in system.positive or not (v.is_number and v.is_real and float(v) < 0)
