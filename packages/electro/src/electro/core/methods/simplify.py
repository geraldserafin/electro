"""Simplifying as a book does, by equivalent circuits: two elements replaced by the one they are, seen from
where they meet the rest. The rules (series, parallel, sources in series) are found by ``matches``, not
written down."""

from __future__ import annotations

import itertools
from collections.abc import Collection, Iterator
from dataclasses import dataclass

import sympy as sp

from ..circuit.elements import Capacitor, CurrentSource, Inductor, Resistor, VoltageSource
from ..circuit.kind import Kind
from ..circuit.netlist import Netlist
from ..circuit.tree import GND, Element, Net, Node
from ..circuit.wiring import rebuild
from ..problem.problem import Problem
from ..problem.quantities import element_of, points_of
from ..solver.analysis import AC, DC, Analysis
from ..solver.expressions import subs
from ..solver.port import matches, port
from ..solver.symbols import Symbols, symbols
from ..solver.system import parameter_values

EQUIVALENTS = (Resistor, Capacitor, Inductor, VoltageSource, CurrentSource)
"""What two elements may become, in this order: a resistor first (an impedance, in AC)."""


@dataclass(frozen=True)
class Reduction:
    """``value``: the new element's parameter in the replaced ones' (R₂·R₃₄/(R₂+R₃₄)); ``amount``: with
    the data in."""

    how: str
    replaced: tuple[Element, Element]
    by: Element
    value: sp.Expr
    amount: sp.Expr


@dataclass(frozen=True)
class _Pair:
    """Elements ``i`` and ``j``, in ``how`` (``"series"`` or ``"parallel"``), between points ``a`` and ``b``."""

    how: str
    i: int
    j: int
    a: int
    b: int


def simplify(
    problem: Problem, keep: Collection[Element] = (), analysis: DC | AC | None = None
) -> tuple[Problem, tuple[Reduction, ...]]:
    """The problem on a smaller circuit that behaves alike where it is asked about, and the steps there.
    What is sought, and ``keep``, stays as it is."""
    steps: list[Reduction] = []
    while (found := _step(problem, keep, analysis or DC())) is not None:
        problem, reduction = found
        steps.append(reduction)
    return problem, tuple(steps)


def _step(problem: Problem, keep: Collection[Element], analysis: Analysis) -> tuple[Problem, Reduction] | None:
    s = symbols(problem.circuit)
    for pair in _pairs(s.net, _untouchable(problem, keep), _asked_points(problem)):
        relation = port(s, (pair.i, pair.j), pair.a, pair.b, analysis)
        if relation is None:
            continue
        for kind in EQUIVALENTS:
            value = matches(relation, kind, analysis)
            if value is not None:
                return _replaced(problem, s, pair, kind, value)
    return None


def _pairs(net: Netlist, untouchable: set[Element], asked: set[Node | Net]) -> Iterator[_Pair]:
    """Two elements that may be one: on the same two points (parallel), or meeting at a point nothing
    else touches (series)."""
    two = [(i, *ns) for i, (e, ns) in enumerate(net.parts) if len(ns) == 2 and e not in untouchable]
    for (i, a, b), (j, c, d) in itertools.combinations(two, 2):
        if {a, b} == {c, d} and a != b:
            yield _Pair("parallel", i, j, a, b)
        for mid in {a, b} & {c, d}:
            if len({a, b, c, d}) == 3 and _only_between(net, mid, asked):
                yield _Pair("series", i, j, a if b == mid else b, c if d == mid else d)


def _only_between(net: Netlist, point: int, asked: set[Node | Net]) -> bool:
    """Two ends meet there and nothing else: not ground, nothing asked of it."""
    ends = [n for _, ns in net.parts for n in ns]
    return ends.count(point) == 2 and dict(net.named).get(point) not in (GND, *asked)


def _replaced(problem: Problem, s: Symbols, pair: _Pair, kind: Kind, value: sp.Expr) -> tuple[Problem, Reduction]:
    e, f = s.net.parts[pair.i][0], s.net.parts[pair.j][0]
    by = kind(_combined(s.labels[pair.i], s.labels[pair.j]))
    parts = [p for k, p in enumerate(s.net.parts) if k not in (pair.i, pair.j)] + [(by, (pair.a, pair.b))]
    names = {x.name for x, _ in parts}
    given = {
        k: v
        for k, v in problem.given.items()
        if k is not e and k is not f and not (isinstance(k, str) and k not in names)
    }
    amount = sp.simplify(subs(value, parameter_values(problem, s)))
    simpler = Problem(rebuild(parts, s.net.named), {**given, by: amount}, problem.find)
    return simpler, Reduction(pair.how, (e, f), by, value, amount)


def _untouchable(problem: Problem, keep: Collection[Element]) -> set[Element]:
    """What a step may not touch: what is asked about, what a condition speaks of, what was said."""
    conditions = [k for k in problem.given if not isinstance(k, Element | str)]
    spoken_of = {element_of(q) for q in (*problem.find, *conditions)}
    return set(keep) | {e for e in spoken_of if e is not None}


def _asked_points(problem: Problem) -> set[Node | Net]:
    return {p for q in problem.find for p in points_of(q)}


def _combined(a: str, b: str) -> str:
    """A book's name for what two make: R_3 and R_4 make R_34 (else both side by side)."""
    (x, _, m), (y, _, n) = a.partition("_"), b.partition("_")
    return f"{x}_{m}{n}" if x == y and m and n else f"{a}{b}"
