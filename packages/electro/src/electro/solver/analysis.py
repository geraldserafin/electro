"""A frame: how a law's time words become an equation of one frame. ``D`` is the difference back over the
frame, ``Pre`` what was a frame ago. A frame is nothing but how long it is (``dt``) and what was a frame ago
(``ago``): one infinitely long has settled (``DC``); one infinitely short (``dt`` 0) is read in the limit.
Nothing here knows any element or any kind of signal: ``methods.ac`` is a frame like any other.
"""

from __future__ import annotations

from dataclasses import dataclass, fields

import sympy as sp

from ..circuit.time import D, Pre
from .expressions import expr, replace, symbols_in

DT = sp.Symbol("dt", positive=True)


@dataclass(frozen=True)
class Step:
    """A frame ``dt`` long after another (given, or rest): what was a frame ago is a letter, ``x⁻``."""

    dt: sp.Expr = DT

    def ago(self, x: sp.Expr) -> sp.Expr:
        """``x`` a frame ago."""
        return before(x)

    def timed(self, law: sp.Expr) -> sp.Expr:
        """The law, its data in, as this frame reads what changes in time: as it is."""
        return law

    def product(self, a: sp.Expr, b: sp.Expr) -> sp.Expr:
        """Two quantities multiplied (a power: a voltage and a current), as this frame reads it."""
        return a * b

    def letters(self) -> set[sp.Symbol]:
        """The letters the frame itself brings (its length, …): never to be found."""
        return {x for f in fields(self) for x in symbols_in(expr(getattr(self, f.name)))}


@dataclass(frozen=True)
class DC(Step):
    """One frame, infinitely long: whatever changes has stopped changing."""

    dt: sp.Expr = sp.oo


Analysis = Step


def before(x: sp.Expr) -> sp.Symbol:
    """``x`` a step ago: what a step in time remembers."""
    return sp.Symbol(f"{x}⁻")


def is_before(x: sp.Symbol) -> bool:
    return x.name.endswith("⁻")


def interpret(law: sp.Expr, frame: Step) -> sp.Expr:
    """``D`` and ``Pre`` read in ``frame``; one infinitely short in the limit, its length ``DT`` → 0."""
    short = frame.dt == 0

    def limit(e: sp.Expr) -> sp.Expr:
        return sp.limit(e, DT, 0) if short else e

    length = DT if short else frame.dt
    return replace(replace(law, D, lambda x: limit((x - frame.ago(x)) / length)), Pre, lambda x: limit(frame.ago(x)))
