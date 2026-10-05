"""A hole filled: the simplest element that fits where an unknown one is."""

from __future__ import annotations

from dataclasses import dataclass

from ..circuit.elements import CurrentSource, Open, Resistor, VoltageSource, Wire
from ..circuit.kind import Kind
from ..circuit.tree import Element, netlist
from ..circuit.wiring import rebuild
from ..problem.problem import Problem
from ..problem.quantities import Parameter
from ..solver.analysis import AC, DC
from ..solver.errors import Undetermined
from ..solver.solution import Solution
from ..solver.solve import solve

SIMPLEST_FIRST = (Wire, Open, Resistor, VoltageSource, CurrentSource)


@dataclass(frozen=True)
class Filled:
    problem: Problem
    by: Element
    solution: Solution


def fill(problem: Problem, hole: Element, analysis: DC | AC | None = None) -> Filled:
    """The first of ``SIMPLEST_FIRST`` that the data do not contradict and pin down."""
    for kind in SIMPLEST_FIRST:
        filled, by = _filled_with(problem, hole, kind)
        try:
            solution = solve(filled, analysis)
        except Undetermined:
            continue
        if _pinned(solution, by):
            return Filled(filled, by, solution)
    raise Undetermined("no simple element fits where the hole is")


def _filled_with(problem: Problem, hole: Element, kind: Kind) -> tuple[Problem, Element]:
    net = netlist(problem.circuit)
    by = kind(hole.name)
    parts = [(by, ns) if e is hole else (e, ns) for e, ns in net.parts]
    given = {k: v for k, v in problem.given.items() if k is not hole}
    return Problem(rebuild(parts, net.named), given, problem.find), by


def _pinned(solution: Solution, e: Element) -> bool:
    """Every parameter of ``e`` found, none left free."""
    try:
        for w in e.kind.parameters:
            solution(Parameter(e, w))
    except Undetermined:
        return False
    return True
