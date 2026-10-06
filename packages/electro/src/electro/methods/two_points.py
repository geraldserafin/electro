"""A circuit seen from two of its points: the relation there, the one resistor it is, its Thévenin
equivalent."""

from __future__ import annotations

from dataclasses import dataclass

import sympy as sp

from ..circuit.elements import Resistor
from ..circuit.tree import Net, Node
from ..problem.problem import Problem
from ..solver.analysis import DC, Analysis
from ..solver.expressions import subs
from ..solver.port import PORT_I, PORT_U, matches, port
from ..solver.relation import Equation, Relation
from ..solver.symbols import symbols
from ..solver.system import parameter_values


@dataclass(frozen=True)
class Thevenin:
    """``E``: the voltage at its ends with nothing taken; ``Z``: how it drops with the current taken."""

    E: sp.Expr
    Z: sp.Expr


def between(problem: Problem, a: Node | Net, b: Node | Net, analysis: Analysis | None = None) -> Relation | None:
    """A current let in at ``a`` and out at ``b``, the data in."""
    s = symbols(problem.circuit)
    pa, pb = (next(n for n, q in s.net.named if q == x) for x in (a, b))
    relation = port(s, range(len(s.net.parts)), pa, pb, analysis or DC())
    if relation is None:
        return None
    values = parameter_values(problem, s)
    return Relation(relation.ends, tuple(Equation(subs(eq.expr, values), eq.origin) for eq in relation.equations))


def resistance(relation: Relation | None, analysis: Analysis | None = None) -> sp.Expr | None:
    """The one resistor (an impedance, in AC) a black box is, if it is one."""
    return matches(relation, Resistor, analysis) if relation is not None else None


def thevenin(relation: Relation | None) -> Thevenin | None:
    """``U = E − Z·I``, I taken out of its first end."""
    if relation is None or len(relation.equations) != 1:
        return None
    us = sp.solve(relation.equations[0].expr, PORT_U)
    if len(us) != 1:
        return None
    u = sp.expand(us[0])
    return Thevenin(sp.simplify(u.subs(PORT_I, 0)), sp.simplify(u.diff(PORT_I)))
