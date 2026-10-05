"""Superposition: a quantity as the sum of what each independent source makes of it alone."""

from __future__ import annotations

from dataclasses import dataclass

import sympy as sp

from ..circuit.tree import Element, netlist
from ..problem.problem import Problem
from ..problem.quantities import Quantity
from ..solver.analysis import AC, DC
from ..solver.errors import NotLinear
from ..solver.laws import is_linear, is_source
from ..solver.solve import solve


@dataclass(frozen=True)
class Superposition:
    """``parts``: each source alone (the others zero) and its share."""

    quantity: Quantity
    parts: tuple[tuple[Element, sp.Expr], ...]
    total: sp.Expr


def superposition(problem: Problem, q: Quantity, analysis: DC | AC | None = None) -> Superposition:
    elements = [e for e, _ in netlist(problem.circuit).parts]
    nonlinear = next((e for e in elements if not is_linear(e, analysis)), None)
    if nonlinear is not None:
        raise NotLinear(nonlinear)
    sources = [e for e in elements if is_source(e)]
    parts = tuple((s, _alone(problem, s, sources, q, analysis)) for s in sources)
    return Superposition(q, parts, sp.simplify(sp.Add(*(v for _, v in parts))))


def _alone(problem: Problem, source: Element, sources: list[Element], q: Quantity, analysis: DC | AC | None) -> sp.Expr:
    others_off = {o: 0 for o in sources if o is not source}
    return solve(Problem(problem.circuit, {**problem.given, **others_off}), analysis)(q)
