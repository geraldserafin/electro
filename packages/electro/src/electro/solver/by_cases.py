"""Elements of several ways (a textbook diode), solved as by hand: assume a way for each, solve, check that
what each way needs holds; if it does not, the next assumption. The tries are the steps."""

from __future__ import annotations

import itertools
from collections.abc import Sequence
from dataclasses import replace

import sympy as sp

from ..problem.problem import Problem
from .analysis import Analysis
from .by_hand import Known, solve_by_hand
from .errors import Undetermined
from .expressions import subs, symbols_in
from .relation import Origin, Way
from .solution import Solution, SolutionStep
from .system import System

Combination = Sequence[Way]


def solve_by_cases(problem: Problem, system: System, analysis: Analysis) -> Solution:
    tried: list[SolutionStep] = []
    fitting: list[Solution] = []
    for combination in itertools.product(*system.choices):
        assumed = [_said("assumed", w) for w in combination]
        try:
            values, steps = solve_by_hand(_assuming(system, combination))
        except Undetermined:
            tried += [*assumed, _said("rejected", combination[0])]
            continue
        if _floating(combination, values, system):
            continue
        broken = _broken(combination, values)
        if broken is not None:
            tried += [*assumed, *steps, _said("rejected", broken)]
            continue
        checked = [_said("checked", w) for w in combination]
        unknown = frozenset(system.unknowns) - set(values)
        fitting.append(
            Solution(problem, values, unknown, system.symbols, (*tried, *assumed, *steps, *checked), analysis)
        )
    if not fitting:
        raise Undetermined("no way of its elements fits")
    if len(fitting) > 1:
        raise Undetermined("more than one way fits")
    return fitting[0]


def _assuming(system: System, combination: Combination) -> System:
    equations = system.equations + tuple(eq for w in combination for eq in w.equations)
    return replace(system, equations=equations, choices=())


def _checks(combination: Combination, values: Known) -> list[tuple[Way, sp.Expr]]:
    return [(w, sp.simplify(subs(h, values))) for w in combination for h in w.holds]


def _floating(combination: Combination, values: Known, system: System) -> bool:
    """That way leaves part of the circuit floating: nothing decides what it needs."""
    return any(symbols_in(v) & set(system.unknowns) for _, v in _checks(combination, values))


def _broken(combination: Combination, values: Known) -> Way | None:
    """The first way whose need does not hold."""
    checks = _checks(combination, values)
    if any(not v.is_number for _, v in checks):
        raise Undetermined("which way each element is depends on values not given")
    return next((w for w, v in checks if float(v) < -1e-12), None)


def _said(how: str, way: Way) -> SolutionStep:
    what = "assumed" if how == "assumed" else "holds"
    return SolutionStep((), (), (Origin(what, way.element, case=way.name),), how)
