"""The algebra elements are made of: an equation and where it comes from, an element's ways, and sympy's
loose types narrowed once."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import cast

import sympy as sp

from .time import DT, THETA


@dataclass(frozen=True)
class Origin:
    """Where an equation comes from, the reason a step gives: ``what`` is ``"law"`` (an element's
    ``index``-th; ``case``: the way it then is), ``"kcl"`` (Kirchhoff at a point), ``"wire"`` (two ends
    joined), ``"given"`` (a datum), ``"reference"`` (a potential chosen 0), ``"assumed"`` or ``"holds"``;
    ``subject``: the element, the point, the datum's key."""

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
class SolutionStep:
    """What was found, its value, and from which equations (their origins: the reason). ``how``:
    ``"alone"`` (one equation, one unknown), ``"together"`` (several at once), ``"numerically"``, ``"assumed"``
    (an element taken to be one of its ways), ``"checked"`` (what that way needs holds) or ``"rejected"``."""

    found: tuple[sp.Symbol, ...]
    values: tuple[sp.Expr, ...]
    because: tuple[Origin, ...]
    how: str = "alone"
    equations: tuple[sp.Expr, ...] = ()
    """Each origin's equation (= 0), as it was."""


@dataclass(frozen=True)
class Case:
    """One way an element may be (a diode on, or off): its laws then, and what must hold for it to be that
    way, each ``holds`` ≥ 0."""

    name: str
    laws: tuple[sp.Expr, ...]
    holds: tuple[sp.Expr, ...] = ()


@dataclass(frozen=True)
class Cases:
    """An element of several ways (piecewise: the textbook's diode). The circuit decides which: the one
    whose ``holds`` hold."""

    cases: tuple[Case, ...]


@dataclass(frozen=True)
class Way:
    """One way an element may be, within a circuit: its equations then, and what must hold (≥ 0)."""

    element: object
    name: str
    equations: tuple[Equation, ...]
    holds: tuple[sp.Expr, ...]


def ways(laws: Sequence[sp.Expr] | Cases) -> tuple[Case, ...]:
    """Laws as ways: plain laws are one way, of no name."""
    if isinstance(laws, Cases):
        return tuple(Case(c.name, tuple(map(expr, c.laws)), tuple(map(expr, c.holds))) for c in laws.cases)
    return (Case("", tuple(map(expr, laws))),)


def normal(e: sp.Expr) -> sp.Expr:
    """An expression as short as it cheaply gets: over one denominator, cancelled, when a letter divides it
    (0 then when it always is; the denominator kept — cleared, its zeros would be roots that are none);
    expanded otherwise, an exponential of a sum never split into a product (e^(u−5) as e^u·e^−5: one huge,
    one tiny). A frame's length and how it reads a change never: x/dt is 0 in a frame infinitely long, x·dt/dt is not."""
    if e.atoms(sp.Function) or not any(
        p.exp.is_negative and p.base.free_symbols - {DT, THETA} for p in e.atoms(sp.Pow)
    ):
        return sp.expand(e, power_exp=False)
    return sp.cancel(e)


def expr(x: object) -> sp.Expr:
    return cast(sp.Expr, sp.sympify(x))


def subs(x: sp.Expr, values: Mapping[sp.Symbol, sp.Expr] | Mapping[sp.Symbol, float]) -> sp.Expr:
    return cast(sp.Expr, x.subs(list(values.items())))


def symbols_in(x: object) -> set[sp.Symbol]:
    return {s for s in expr(x).free_symbols if isinstance(s, sp.Symbol)}
