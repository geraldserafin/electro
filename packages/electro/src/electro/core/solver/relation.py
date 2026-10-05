"""A relation (the category Rel, DESIGN.md §13): variables and equations, each equation knowing where it
comes from, so that a solution can say its steps."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass

import sympy as sp

from ..circuit.tree import Element


@dataclass(frozen=True)
class Origin:
    """Where an equation comes from, the reason a step gives.

    ``what`` is ``"law"`` (an element's ``index``-th; ``case``: the way the element then is), ``"kcl"``
    (Kirchhoff at a point), ``"given"`` (a datum), ``"port"``, ``"assumed"`` or ``"holds"``; ``subject`` is
    what it is about: the element, the point's number, the datum's key."""

    what: str
    subject: object
    index: int = 0
    case: str = ""


@dataclass(frozen=True)
class Equation:
    """``expr`` = 0."""

    expr: sp.Expr
    origin: Origin


@dataclass(frozen=True)
class Way:
    """One way an element may be, within a relation: its equations then, and what must hold (≥ 0)."""

    element: Element
    name: str
    equations: tuple[Equation, ...]
    holds: tuple[sp.Expr, ...]


@dataclass(frozen=True)
class Relation:
    """``ends`` are the variables seen from outside, the rest are inside. ``choices``: for each element
    of several ways, its ways. The relation is the union of one piece per choice of a way for each."""

    ends: tuple[sp.Symbol, ...]
    equations: tuple[Equation, ...]
    choices: tuple[tuple[Way, ...], ...] = ()


def join(*relations: Relation) -> Relation:
    """Every equation of each; a variable they share is one, which is how they are joined."""
    ends = tuple(dict.fromkeys(x for r in relations for x in r.ends))
    equations = tuple(eq for r in relations for eq in r.equations)
    return Relation(ends, equations, tuple(c for r in relations for c in r.choices))


def hide(r: Relation, ends: Sequence[sp.Symbol]) -> Relation:
    """Seen from outside only through ``ends``."""
    return Relation(tuple(ends), r.equations, r.choices)


def all_equations(r: Relation) -> Iterator[Equation]:
    """Every equation, each way's too."""
    yield from r.equations
    for choice in r.choices:
        for way in choice:
            yield from way.equations
