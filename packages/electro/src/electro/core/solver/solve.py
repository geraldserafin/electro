"""Where a circuit settles (DC), or its phasors (AC), and the steps there. Linear: by algebra, step by
step; elements of several ways: by cases; beyond algebra (a diode's exp): by Newton."""

from __future__ import annotations

import sympy as sp

from ..circuit.time import TIME, Pre
from ..problem.problem import Problem
from .analysis import AC, DC
from .by_cases import solve_by_cases
from .by_hand import solve_by_hand
from .errors import Contradiction, NotLinear, Undetermined
from .expressions import symbols_in
from .newton import compiled, homotopy
from .relation import all_equations
from .solution import Solution, SolutionStep
from .system import SOURCES, System, equations, relation


def solve(problem: Problem, analysis: DC | AC | None = None) -> Solution:
    analysis = analysis or DC()
    if _has_memory(problem):
        raise Undetermined("it has memory — what it holds depends on what came before: simulate it")
    system = equations(problem, analysis)
    if any(eq.expr.has(TIME) for eq in system.equations):
        raise Undetermined("its data change in time: simulate it")
    if system.choices:
        return solve_by_cases(problem, system, analysis)
    if _is_algebraic(system):
        return _by_algebra(problem, system, analysis)
    if isinstance(analysis, AC):
        raise NotLinear("a phasor of a non-linear circuit: around its working point (not yet)")
    return _by_newton(problem)


def _has_memory(problem: Problem) -> bool:
    """A law speaks of what came before (a flip-flop holds what it was last given)."""
    return any(eq.expr.has(Pre) for eq in all_equations(relation(problem.circuit)))


def _is_algebraic(system: System) -> bool:
    """Polynomial in its unknowns (an unknown resistance times a current too)."""
    try:
        for eq in system.equations:
            sp.Poly(eq.expr, *system.unknowns)
        return True
    except sp.PolynomialError:
        return False


def _by_algebra(problem: Problem, system: System, analysis: DC | AC) -> Solution:
    try:
        values, steps = solve_by_hand(system)
    except Contradiction as err:
        raise Contradiction(str(err), _clashing(problem, analysis)) from None
    unknown = frozenset(system.unknowns) - set(values)
    return Solution(problem, values, unknown, system.symbols, steps, analysis)


def _clashing(problem: Problem, analysis: DC | AC) -> list[object]:
    """The given data that clash: those without which it fits."""
    return [key for key in problem.given if _fits_without(problem, key, analysis)]


def _fits_without(problem: Problem, key: object, analysis: DC | AC) -> bool:
    rest = Problem(problem.circuit, {k: v for k, v in problem.given.items() if k is not key}, problem.find)
    try:
        solve_by_hand(equations(rest, analysis))
    except Undetermined:
        return False
    return True


def _by_newton(problem: Problem) -> Solution:
    """Every value is needed; the sources are raised from nothing."""
    raised = equations(problem, DC(), sources=SOURCES)
    exprs = [eq.expr for eq in raised.equations]
    unknowns = list(raised.unknowns)
    if any(x not in {*unknowns, SOURCES} for e in exprs for x in symbols_in(e)):
        raise Undetermined("a non-linear circuit is solved with every value given")
    f, j = compiled(exprs, unknowns, (SOURCES,))
    found = homotopy(f, j, len(unknowns))
    if found is None:
        raise Undetermined("Newton did not get there")
    values = {u: sp.Float(v) for u, v in zip(unknowns, found)}
    step = SolutionStep(
        tuple(values), tuple(values.values()), tuple(eq.origin for eq in raised.equations), "numerically"
    )
    return Solution(problem, values, frozenset(), raised.symbols, (step,))
