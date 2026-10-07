"""Equations, why each holds, and the laws of a whole circuit."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

import sympy as sp


@dataclass(frozen=True)
class Origin:
    """Why an equation holds. ``what``: ``"law"`` (an element's ``index``-th law; ``case``: which of its ways),
    ``"kcl"`` (Kirchhoff at a point), ``"given"`` (a datum), ``"reference"`` (a potential set to 0), ``"end"``,
    ``"assumed"`` or ``"holds"``. ``subject``: the element, the point or the datum's key."""

    what: str
    subject: object
    index: int = 0
    case: str = ""


@dataclass(frozen=True)
class Equation:
    """``expr`` = 0, and why."""

    expr: sp.Expr
    origin: Origin

    def map(self, f: Callable[[sp.Expr], sp.Expr]) -> Equation:
        return Equation(f(self.expr), self.origin)


@dataclass(frozen=True)
class Way:
    """One way an element of several may be (a diode on, or off): its equations then, and what must hold for
    it (each ``holds`` ≥ 0)."""

    element: object
    name: str
    equations: tuple[Equation, ...]
    holds: tuple[sp.Expr, ...]

    def map(self, f: Callable[[sp.Expr], sp.Expr]) -> Way:
        return Way(self.element, self.name, tuple(q.map(f) for q in self.equations), tuple(map(f, self.holds)))


@dataclass(frozen=True)
class Laws:
    """A closed circuit's laws: its ``equations``; its elements of several ways, each one's ``ways``; ``at``:
    each element terminal's potential as the potential of the point it is on."""

    equations: tuple[Equation, ...]
    ways: tuple[tuple[Way, ...], ...]
    at: Mapping[sp.Symbol, sp.Expr]

    def map(self, f: Callable[[sp.Expr], sp.Expr]) -> Laws:
        """Every expression through ``f`` (a frame's reading, values put in)."""
        ways = tuple(tuple(w.map(f) for w in c) for c in self.ways)
        return Laws(tuple(q.map(f) for q in self.equations), ways, self.at)

    def expressions(self) -> list[sp.Expr]:
        """Every expression in them, the ways' too."""
        ways = [e for c in self.ways for w in c for e in (*(q.expr for q in w.equations), *w.holds)]
        return [q.expr for q in self.equations] + ways
