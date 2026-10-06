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
from .compose import framed
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
    """The circuit's component (``compose``), read in the frame with the data, what is left solved, every
    variable back through what was eliminated."""
    framed_ = framed(problem, analysis, frame)
    system = framed_.system
    if any(eq.expr.has(TIME) for eq in system.equations) or any(v.has(TIME) for _, v, _ in framed_.definitions):
        raise Undetermined("its data change in time: simulate it")
    if system.choices:
        solution = solve_by_cases(problem, system, analysis)
    elif _is_algebraic(system):
        solution = _by_algebra(problem, system, analysis)
    elif analysis.dt == 0:
        raise NotLinear("a non-linear circuit in frames infinitely short: around its working point (not yet)")
    else:
        framed_ = framed(problem, analysis, frame, sources=SOURCES)
        solution = _by_newton(problem, framed_.system, analysis)
    values = framed_.complete(solution.values)
    unknown = frozenset(solution.unknowns | {x for x, v in values.items() if symbols_in(v) & solution.unknowns})
    worked = _traced(solution.steps, framed_.definitions, values, unknown)
    return replace(solution, values=values, unknowns=unknown, worked=worked, time=frame.get(TIME, sp.oo))


def _traced(found, definitions, values, unknown) -> tuple[SolutionStep, ...]:
    """The steps as the solving left them: what was found of what was left, then each eliminated quantity a
    book names (an element's current, a point's potential — never a wire's own), its value now known, each
    once all it is worked out from is."""
    shown: set[sp.Symbol] = set()
    waiting = []
    for x, _, eq in definitions:
        value = values.get(x)
        named = not isinstance(x, sp.Dummy) and eq.origin.what != "wire"
        if named and x not in shown and value is not None and not symbols_in(value) & unknown:
            shown.add(x)
            waiting.append((x, value, eq))
    known = {x for step in found for x in step.found}
    eliminated = []
    while waiting:
        ready = next(
            (w for w in waiting if not {y for y in symbols_in(w[2].expr) - {w[0]} if y in shown} - known), waiting[0]
        )
        waiting.remove(ready)
        x, value, eq = ready
        known.add(x)
        eliminated.append(SolutionStep((x,), (value,), (eq.origin,), equations=(eq.expr,)))
    checks = next((k for k, st in enumerate(reversed(found)) if st.how != "checked"), len(found))
    return (*found[: len(found) - checks], *eliminated, *found[len(found) - checks :])


def solve_step(problem: Problem) -> Solution:
    """Φ as a formula: the step solved in letters — ``dt``, ``t``, what was a step before."""
    system = equations(problem, Step())
    if system.choices or not _is_algebraic(system):
        raise NotLinear("a step of a non-linear circuit has no formula: Newton finds it (call the step)")
    return _by_algebra(problem, system, Step())


def _is_algebraic(system: System) -> bool:
    """Polynomial in its unknowns (an unknown resistance times a current too)."""
    if not system.unknowns:
        return True
    try:
        for eq in system.equations:
            sp.Poly(sp.numer(sp.together(eq.expr)), *system.unknowns)
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


def _by_newton(problem: Problem, raised: System, analysis: Step) -> Solution:
    """Every value is needed; the sources are raised from nothing."""
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
