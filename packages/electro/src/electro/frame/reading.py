"""A frame: how a law's time words become an equation of one frame. ``D`` is the change over the frame —
with ``theta`` ½, the slope a trapezoid gives, the mean of the slopes at its two ends being the change over
it, so error falls as dt²; with 1, the plain difference back (backward Euler, for a frame after a jump) —
``Pre`` what was a frame ago; a frame is nothing but how long it is (``dt``) and what was a frame ago
(``ago``). One infinitely long has settled (``DC``); in AC frames go on forever under sines of ω, each the one
before turned by ω·dt, infinitely short — ``D`` comes out jω, found as the limit, not told.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import cast

import sympy as sp

from ..circuit.algebra import symbols_in
from ..circuit.time import DT, TIME, D, Pre


@dataclass(frozen=True)
class Step:
    """A frame ``dt`` long after another (given, or rest): what was a frame ago is a letter, ``x⁻``; a
    change read by ``theta`` (1: back over the frame; ½: trapezoids, with the slope a frame ago, ``D(x)⁻``)."""

    dt: sp.Expr = DT
    theta: sp.Expr = sp.Integer(1)

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
        return {x for f in fields(self) for x in symbols_in(getattr(self, f.name))}


@dataclass(frozen=True)
class DC(Step):
    """One frame, infinitely long: whatever changes has stopped changing."""

    dt: sp.Expr = sp.oo


@dataclass(frozen=True, init=False)
class AC(Step):
    """Frames forever under sines of the angular frequency ``omega`` (a number is read as one), each the one
    before turned by ω·dt — a phasor — infinitely short. A sine in time is its phasor, a power the average over
    a period."""

    omega: sp.Expr

    def __init__(self, omega: object) -> None:
        object.__setattr__(self, "dt", sp.Integer(0))
        object.__setattr__(self, "theta", sp.Integer(1))
        object.__setattr__(self, "omega", sp.sympify(omega))

    def ago(self, x: sp.Expr) -> sp.Expr:
        return x * sp.exp(-sp.I * self.omega * DT)

    def timed(self, law: sp.Expr) -> sp.Expr:
        return phasors(law, self.omega)

    def product(self, a: sp.Expr, b: sp.Expr) -> sp.Expr:
        """Of phasors: ½·Re(a·b*)."""
        return sp.re(sp.expand(a * sp.conjugate(b), complex=True)) / 2


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
    theta = frame.theta

    def change(x: sp.Expr) -> sp.Expr:
        return limit(((x - frame.ago(x)) / length - (1 - theta) * slope(x)) / theta)

    return law.replace(D, change).replace(Pre, lambda x: limit(frame.ago(x)))


def slope(x: sp.Expr) -> sp.Symbol:
    """How fast ``x`` changed a step ago, at the end of that step (what trapezoids remember)."""
    return before(D(x))


def phasors(law: sp.Expr, omega: sp.Expr) -> sp.Expr:
    """A sine in time, sin(ω·t + φ), read as its phasor e^(jφ) (a cosine is a quarter ahead); one of another
    frequency is not there at ω."""

    def phasor(e: sp.Expr) -> sp.Expr:
        arg = cast(sp.Expr, e.args[0])
        w, phase = sp.diff(arg, TIME), cast(sp.Expr, arg.subs(TIME, 0))
        if omega.is_number and w.is_number and sp.simplify(w - omega) != 0:
            return sp.Integer(0)
        return sp.exp(sp.I * (phase + (0 if isinstance(e, sp.sin) else sp.pi / 2)))

    return cast(sp.Expr, law.replace(lambda e: isinstance(e, sp.sin | sp.cos) and TIME in e.free_symbols, phasor))


def frequencies(law: sp.Expr) -> set[sp.Expr]:
    """The angular frequencies of the sines in time in ``law``."""
    return {sp.diff(e.args[0], TIME) for e in law.atoms(sp.sin, sp.cos) if TIME in e.free_symbols}
