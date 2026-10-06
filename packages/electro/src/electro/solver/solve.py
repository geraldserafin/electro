"""A frame of a circuit, from its laws alone: where it settles (DC, one frame infinitely long), or a frame
after another (``Step``), or any other frame (``analysis``). Linear: by algebra, step by step; elements of
several ways: by cases; beyond algebra: by Newton."""

from __future__ import annotations

from dataclasses import replace

import sympy as sp

from ..circuit.time import TIME, D, Pre
from ..problem.problem import Key, Problem
from .analysis import DC, Step
from .analysis import before as before_of
from .by_cases import solve_by_cases
from .by_hand import solve_by_hand
from .errors import Contradiction, NotLinear, Undetermined
from .expressions import expr, symbols_in
from .numeric import compile_equations, homotopy
from .relation import all_equations
from .solution import Solution, SolutionStep
from .system import SOURCES, System, equations, relation


def solve(problem: Problem, analysis: Step | None = None, before: Solution | None = None) -> Solution:
    """One frame of the circuit, ``analysis`` (by default DC: one frame infinitely long, all settled), after
    ``before`` (by default from rest — every capacitor empty, every inductor still). A simulation is nothing
    but frames, each solved after the one before (``simulate`` runs it compiled: ``solver.step``)."""
    analysis = analysis or DC()
    try:
        return _solve(problem, analysis, _frame(problem, analysis, before))
    except Undetermined as err:
        err.problem = problem
        raise


def _frame(problem: Problem, analysis: Step, before: Solution | None) -> dict[sp.Symbol, sp.Expr]:
    """What a frame starts from: what each remembered quantity was (``before``'s, or nothing at rest), and the
    time at its end — none for a frame infinitely long or short."""
    remembered = {expr(a.args[0]) for eq in all_equations(relation(problem.circuit)) for a in eq.expr.atoms(D, Pre)}
    was = {before_of(x): before.evaluated(x) if before is not None else sp.Integer(0) for x in remembered}
    start = before.time if before is not None else sp.Integer(0)
    return was | ({TIME: start + analysis.dt} if analysis.dt not in (0, sp.oo) else {})


def _solve(problem: Problem, analysis: Step, frame: dict[sp.Symbol, sp.Expr]) -> Solution:
    system = equations(problem, analysis, letters=frame)
    if any(eq.expr.has(TIME) for eq in system.equations):
        raise Undetermined("its data change in time: simulate it")
    if system.choices:
        solution = solve_by_cases(problem, system, analysis)
    elif _is_algebraic(system):
        solution = _by_algebra(problem, system, analysis)
    elif analysis.dt == 0:
        raise NotLinear("a non-linear circuit in frames infinitely short: around its working point (not yet)")
    else:
        solution = _by_newton(problem, analysis, frame)
    return replace(solution, time=frame.get(TIME, sp.oo))


def solve_step(problem: Problem) -> Solution:
    """Φ as a formula: the step solved in letters — ``dt``, ``t``, what was a step before."""
    system = equations(problem, Step())
    if system.choices or not _is_algebraic(system):
        raise NotLinear("a step of a non-linear circuit has no formula: Newton finds it (call the step)")
    return _by_algebra(problem, system, Step())


def _is_algebraic(system: System) -> bool:
    """Polynomial in its unknowns (an unknown resistance times a current too)."""
    try:
        for eq in system.equations:
            sp.Poly(eq.expr, *system.unknowns)
        return True
    except sp.PolynomialError:
        return False


def _by_algebra(problem: Problem, system: System, analysis: Step) -> Solution:
    try:
        values, steps = solve_by_hand(system)
    except Contradiction as err:
        raise Contradiction(str(err), _clashing(problem, analysis)) from None
    unknown = frozenset(system.unknowns) - set(values)
    return Solution(problem, values, unknown, system.symbols, steps, analysis)


def _clashing(problem: Problem, analysis: Step) -> list[Key]:
    """The given data that clash: those without which it fits."""
    return [key for key in problem.given if _fits_without(problem, key, analysis)]


def _fits_without(problem: Problem, key: Key, analysis: Step) -> bool:
    rest = Problem(problem.circuit, {k: v for k, v in problem.given.items() if k is not key}, problem.find)
    try:
        solve_by_hand(equations(rest, analysis))
    except Undetermined:
        return False
    return True


def _by_newton(problem: Problem, analysis: Step, frame: dict[sp.Symbol, sp.Expr]) -> Solution:
    """Every value is needed; the sources are raised from nothing."""
    raised = equations(problem, analysis, sources=SOURCES, letters=frame)
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
    return Solution(problem, values, frozenset(), raised.symbols, (step,), analysis)
