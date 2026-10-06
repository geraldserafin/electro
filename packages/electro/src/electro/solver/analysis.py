"""The analyses: how a law's time words are read. In a step of time ``D`` is the difference back over it and
``Pre`` the value a step ago; DC is one step, infinitely long — everything settled, so ``D`` is 0. In AC
``D`` is jω (phasors) and ``Pre`` the value itself."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

import sympy as sp

from ..circuit.time import TIME, D, Pre
from .expressions import replace


@dataclass(frozen=True)
class AC:
    """Phasors at the angular frequency ``omega`` (a number is read as one: ``AC(2 * math.pi * 50)``)."""

    omega: sp.Expr

    def __post_init__(self) -> None:
        object.__setattr__(self, "omega", sp.sympify(self.omega))


DT = sp.Symbol("dt", positive=True)


@dataclass(frozen=True)
class Step:
    """One step in time, ``dt`` long: what is under ``D`` the difference back over it."""

    dt: sp.Expr = DT


@dataclass(frozen=True)
class DC(Step):
    """One frame, infinitely long: whatever changes has stopped changing."""

    dt: sp.Expr = sp.oo


Analysis = DC | AC | Step


def before(x: sp.Expr) -> sp.Symbol:
    """``x`` a step ago: what a step in time remembers."""
    return sp.Symbol(f"{x}⁻")


def is_before(x: sp.Symbol) -> bool:
    return x.name.endswith("⁻")


def interpret(law: sp.Expr, analysis: Analysis) -> sp.Expr:
    match analysis:
        case AC(omega):
            return _reading(law, lambda x: sp.I * omega * x, lambda x: x)
        case Step(dt):
            return _reading(law, lambda x: (x - before(x)) / dt, before)
    raise TypeError(analysis)


def _reading(law: sp.Expr, derivative: Callable[[sp.Expr], sp.Expr], previous: Callable[[sp.Expr], sp.Expr]) -> sp.Expr:
    return replace(replace(law, D, derivative), Pre, previous)


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
