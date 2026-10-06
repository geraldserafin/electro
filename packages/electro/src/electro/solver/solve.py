"""Where a circuit settles (DC), its phasors (AC), or its step in time (``Step``: Φ, every frame from the one
before). Linear: by algebra, step by step; elements of several ways: by cases; beyond algebra (a diode's
exp): by Newton."""

from __future__ import annotations

from typing import overload

import sympy as sp

from ..circuit.time import TIME, Pre
from ..problem.problem import Key, Problem
from .analysis import AC, DC, Step, frequencies
from .by_cases import solve_by_cases
from .by_hand import solve_by_hand
from .errors import Contradiction, NotLinear, Undetermined
from .expressions import symbols_in
from .numeric import compile_equations, homotopy
from .relation import all_equations
from .solution import Solution, SolutionStep
from .step import StepFunction, step_function
from .system import SOURCES, System, equations, relation


@overload
def solve(problem: Problem, analysis: DC | AC | None = None) -> Solution: ...
@overload
def solve(problem: Problem, analysis: Step) -> StepFunction: ...
def solve(problem: Problem, analysis: DC | AC | Step | None = None) -> Solution | StepFunction:
    """``analysis``: by default DC, or with sines in time of one frequency, their phasors at it. At
    ``Step()``: Φ, the step function (``solver.step``)."""
    try:
        if isinstance(analysis, Step):
            return step_function(problem)
        return _solve(problem, analysis or _own_frequency(problem) or DC())
    except Undetermined as err:
        err.problem = problem
        raise


def _solve(problem: Problem, analysis: DC | AC) -> Solution:
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


def solve_step(problem: Problem) -> Solution:
    """Φ as a formula: the step solved in letters — ``dt``, ``t``, what was a step before."""
    system = equations(problem, Step())
    if system.choices or not _is_algebraic(system):
        raise NotLinear("a step of a non-linear circuit has no formula: Newton finds it (call the step)")
    return _by_algebra(problem, system, Step())


def _own_frequency(problem: Problem) -> AC | None:
    found = {w for eq in equations(problem, DC()).equations for w in frequencies(eq.expr)}
    return AC(found.pop()) if len(found) == 1 else None


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


def _by_algebra(problem: Problem, system: System, analysis: DC | AC | Step) -> Solution:
    try:
        values, steps = solve_by_hand(system)
    except Contradiction as err:
        raise Contradiction(str(err), _clashing(problem, analysis)) from None
    unknown = frozenset(system.unknowns) - set(values)
    return Solution(problem, values, unknown, system.symbols, steps, analysis)


def _clashing(problem: Problem, analysis: DC | AC | Step) -> list[Key]:
    """The given data that clash: those without which it fits."""
    return [key for key in problem.given if _fits_without(problem, key, analysis)]


def _fits_without(problem: Problem, key: Key, analysis: DC | AC | Step) -> bool:
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
    numeric = compile_equations(exprs, unknowns, [SOURCES], raised.symbols.potentials, limited=False)
    found = homotopy(lambda x0, lam: numeric.newton(x0, [lam]), len(numeric.unknowns))
    if found is None:
        raise Undetermined("Newton did not get there")
    values = {u: sp.Float(v) for u, v in zip(numeric.unknowns, found) if u in unknowns}
    step = SolutionStep(
        tuple(values), tuple(values.values()), tuple(eq.origin for eq in raised.equations), "numerically"
    )
    return Solution(problem, values, frozenset(), raised.symbols, (step,))
