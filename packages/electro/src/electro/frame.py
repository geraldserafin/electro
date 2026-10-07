"""Frames: how the time words in a law (``D``, the change; ``Pre``, the value a moment ago) become an equation
of one frame.

- ``Step(dt, θ)``: a frame ``dt`` long after another. ``x⁻`` is ``x`` a frame ago, ``D(x)⁻`` how fast it
  changed then. θ = 1 reads a change back over the frame (backward Euler); θ = ½ by trapezoids, the mean of the
  slopes at the frame's two ends, so the error falls as dt².
- ``DC``: one frame, infinitely long: nothing changes any more.
- ``AC(ω)``: sines of angular frequency ω, as phasors: ``D(x)`` is jω·x.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, fields
from typing import cast

import sympy as sp

from .time import DT, TIME, D, Pre


@dataclass(frozen=True)
class Step:
    """A frame ``dt`` long; ``theta``: 1 back over the frame, ½ by trapezoids."""

    dt: sp.Expr = DT
    theta: sp.Expr = sp.Integer(1)

    def change(self, x: sp.Expr) -> sp.Expr:
        """``D(x)`` in this frame: ((x − x⁻)/dt − (1 − θ)·D(x)⁻)/θ."""
        return ((x - before(x)) / self.dt - (1 - self.theta) * slope(x)) / self.theta

    def ago(self, x: sp.Expr) -> sp.Expr:
        """``Pre(x)`` in this frame: ``x`` a frame ago."""
        return before(x)

    def timed(self, law: sp.Expr) -> sp.Expr:
        """What changes in time in the data (a sine), as this frame reads it: as it is."""
        return law

    def product(self, a: sp.Expr, b: sp.Expr) -> sp.Expr:
        """Two quantities multiplied (a power: a voltage and a current), as this frame reads it."""
        return a * b

    def read(self, law: sp.Expr) -> sp.Expr:
        """``law`` with its time words read in this frame."""
        if not law.has(D, Pre):
            return law
        return law.replace(D, self.change).replace(Pre, self.ago)

    def reading(self, given: Mapping[sp.Symbol, sp.Expr]) -> Callable[[sp.Expr], sp.Expr]:
        """A law read in this frame, ``given`` put in."""
        return lambda e: self.timed(self.read(e).xreplace(given))

    def letters(self) -> set[sp.Symbol]:
        """The letters the frame itself brings (its length…): never unknowns."""
        return {x for f in fields(self) for x in sp.sympify(getattr(self, f.name)).free_symbols}


@dataclass(frozen=True)
class DC(Step):
    """One frame, infinitely long: whatever changes has stopped changing."""

    dt: sp.Expr = sp.oo


@dataclass(frozen=True, init=False)
class AC(Step):
    """Sines of angular frequency ``omega``, read as phasors: a sine in time is its phasor, ``D`` is jω, a power
    is the average over a period."""

    omega: sp.Expr

    def __init__(self, omega: object) -> None:
        object.__setattr__(self, "dt", sp.Integer(0))
        object.__setattr__(self, "theta", sp.Integer(1))
        object.__setattr__(self, "omega", sp.sympify(omega))

    def change(self, x: sp.Expr) -> sp.Expr:
        return sp.I * self.omega * x

    def ago(self, x: sp.Expr) -> sp.Expr:
        return x

    def timed(self, law: sp.Expr) -> sp.Expr:
        return phasors(law, self.omega)

    def product(self, a: sp.Expr, b: sp.Expr) -> sp.Expr:
        """Of phasors: ½·Re(a·b*)."""
        return sp.re(sp.expand(a * sp.conjugate(b), complex=True)) / 2


_BEFORE: dict[sp.Expr, sp.Symbol] = {}


def before(x: sp.Expr) -> sp.Symbol:
    """``x⁻``: ``x`` a frame ago, one letter for each ``x``."""
    return _BEFORE.setdefault(x, sp.Dummy(f"{x}⁻"))


def is_before(x: sp.Symbol) -> bool:
    return x in _BEFORE.values()


def slope(x: sp.Expr) -> sp.Symbol:
    """``D(x)⁻``: how fast ``x`` changed at the end of the frame before (what trapezoids remember)."""
    return before(D(x))


def phasors(law: sp.Expr, omega: sp.Expr) -> sp.Expr:
    """Each sine in time sin(ω·t + φ) as its phasor e^(jφ) (a cosine a quarter ahead); one of another
    frequency is 0 at ω."""

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
