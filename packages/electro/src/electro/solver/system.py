"""A circuit as one relation, and a problem's equations: the relation read by an analysis, the data in.

A circuit's relation joins its elements' laws and, at each point, Kirchhoff's current law: what flows
in from outside is what flows on into the elements there.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import cast

import sympy as sp

from electro.values import UNKNOWN, parse

from ..circuit.elements.parts import Part
from ..circuit.kind import Case
from ..circuit.time import TIME
from ..circuit.tree import Circuit, Element
from ..problem.problem import Problem
from ..problem.quantities import Quantity, Scaled
from .analysis import Analysis, interpret, is_before
from .expressions import expr, subs, symbols_in
from .laws import is_source, ways
from .relation import Equation, Origin, Relation, Way, all_equations
from .symbols import Symbols, symbols

SOURCES = sp.Symbol("λ")
"""How far every independent source is raised: 0 is all off, 1 as given (Newton's way up, ``homotopy``)."""


@dataclass(frozen=True)
class System:
    """``choices`` are read and have the data in too. ``params``: the parameters not given; ``positive``:
    those of them never negative."""

    equations: tuple[Equation, ...]
    unknowns: tuple[sp.Symbol, ...]
    symbols: Symbols
    choices: tuple[tuple[Way, ...], ...] = ()
    positive: frozenset[sp.Symbol] = frozenset()
    params: frozenset[sp.Symbol] = frozenset()


def network(
    s: Symbols, parts: Sequence[int], points: Sequence[int], inflow: Mapping[int, sp.Expr] | None = None
) -> Relation:
    """The relation of the elements ``parts`` meeting at ``points``; ``inflow``: current let in at a
    point from outside."""
    laws: list[Equation] = []
    choices: list[tuple[Way, ...]] = []
    for k in parts:
        e = s.net.parts[k][0]
        cases = ways(e.kind.laws(s.terminals(k), s.params(e)))
        if len(cases) == 1:
            laws += _law_equations(e, cases[0])
        else:
            choices.append(tuple(Way(e, c.name, _law_equations(e, c), c.holds) for c in cases))
    kcl = [_kcl(s, parts, n, (inflow or {}).get(n, sp.Integer(0))) for n in points]
    return Relation((), (*laws, *kcl), tuple(choices))


def relation(c: Circuit) -> Relation:
    """The closed circuit as one relation: nothing seen from outside."""
    s = symbols(c)
    return network(s, range(len(s.net.parts)), [n for n in range(s.net.size) if s.potentials[n] != 0])


def equations(
    problem: Problem,
    analysis: Analysis,
    sources: sp.Expr | int = 1,
    letters: Mapping[sp.Symbol, sp.Expr] | None = None,
) -> System:
    """The problem's equations read by ``analysis``, its data in; every independent source scaled by
    ``sources``; ``letters``: symbols standing for something else — a parameter left as a letter (what is
    set while it runs), what was a step before, the time."""
    s = symbols(problem.circuit)
    values = {**parameter_values(problem, s), **(letters or {})}
    if sources != 1:
        values = _sources_scaled(values, s, sources)
    rel = relation(problem.circuit)
    read = [_read(eq, analysis, values) for eq in (*rel.equations, *_conditions(problem, s))]
    choices = tuple(tuple(_read_way(w, analysis, values) for w in choice) for choice in rel.choices)
    appearing = {x for eq in all_equations(Relation((), tuple(read), choices)) for x in symbols_in(eq.expr)}
    params = _parameters(s) - set(values)
    unknowns = (appearing - _letters(appearing, values, analysis)) | (params & appearing)
    positive = {s.param(e, w) for e, _ in s.net.parts for w in e.kind.positive} & unknowns
    return System(
        tuple(read), tuple(sorted(unknowns, key=str)), s, choices, frozenset(positive), frozenset(params & appearing)
    )


def parameter_values(problem: Problem, s: Symbols) -> dict[sp.Symbol, sp.Expr]:
    """Each parameter's value: as given, else its kind's default."""
    values = {s.param(e, w): expr(parse(d)) for e, _ in s.net.parts for w, d in e.kind.defaults}
    for key, value in problem.given.items():
        if value is UNKNOWN:
            continue
        match key:
            case Element() if isinstance(value, Part):
                values |= {s.param(key, w): expr(parse(x)) for w, x in value.parameters(key.kind.name).items()}
            case Element() if isinstance(value, Mapping):
                values |= {s.param(key, w): cast(sp.Expr, x) for w, x in value.items() if x is not UNKNOWN}
            case Element():
                values[s.param(key)] = cast(sp.Expr, value)
            case str():
                values[sp.Symbol(key)] = cast(sp.Expr, value)
    return values


def _law_equations(e: Element, case: Case) -> tuple[Equation, ...]:
    return tuple(Equation(law, Origin("law", e, i, case.name)) for i, law in enumerate(case.laws))


def _kcl(s: Symbols, parts: Sequence[int], point: int, inflow: sp.Expr) -> Equation:
    into = [current for k in parts for current, n in _ends(s, k) if n == point]
    return Equation(sp.Add(*into) - inflow, Origin("kcl", point))


def _ends(s: Symbols, k: int) -> list[tuple[sp.Expr, int]]:
    """Element ``k``'s terminals: the current into it at each, and the point it is on."""
    e, points = s.net.parts[k]
    currents = s.currents(k)
    return [(currents[t], n) for t, n in zip(e.kind.terminals, points)]


def _conditions(problem: Problem, s: Symbols) -> list[Equation]:
    """The data on quantities, each an equation."""
    return [
        Equation(s.of(key) - _value(value, s), Origin("given", key))
        for key, value in problem.given.items()
        if isinstance(key, Quantity) and value is not UNKNOWN
    ]


def _value(value: object, s: Symbols) -> sp.Expr:
    return s.of(value) if isinstance(value, Quantity | Scaled) else cast(sp.Expr, value)


def _sources_scaled(values: dict[sp.Symbol, sp.Expr], s: Symbols, by: sp.Expr | int) -> dict[sp.Symbol, sp.Expr]:
    of_sources = {p for e, _ in s.net.parts if is_source(e) for p in s.params(e).values()}
    return {p: by * v if p in of_sources else v for p, v in values.items()}


def _parameters(s: Symbols) -> set[sp.Symbol]:
    return {p for e, _ in s.net.parts for p in s.params(e).values()}


def _read(eq: Equation, analysis: Analysis, values: Mapping[sp.Symbol, sp.Expr]) -> Equation:
    return Equation(_reading(eq.expr, analysis, values), eq.origin)


def _reading(e: sp.Expr, analysis: Analysis, values: Mapping[sp.Symbol, sp.Expr]) -> sp.Expr:
    return analysis.timed(subs(interpret(e, analysis), values))


def _read_way(w: Way, analysis: Analysis, values: Mapping[sp.Symbol, sp.Expr]) -> Way:
    holds = tuple(_reading(h, analysis, values) for h in w.holds)
    return Way(w.element, w.name, tuple(_read(eq, analysis, values) for eq in w.equations), holds)


def _letters(appearing: set[sp.Symbol], values: Mapping[sp.Symbol, sp.Expr], analysis: Analysis) -> set[sp.Symbol]:
    """Symbols that appear but are not to be found: letters in the data (a value given as ``R``), the frame's
    own (its length, …), time, what a frame remembers."""
    in_data = {x for v in values.values() for x in symbols_in(expr(v))}
    remembered = {x for x in appearing if is_before(x)}
    return in_data | analysis.letters() | remembered | {TIME}
