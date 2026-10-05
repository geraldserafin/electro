"""The analyses. Each reads a law's time words its own way: ``D`` is 0 in DC, jω in AC, the difference
back over a step in time; ``Pre`` is the value itself in DC and AC, the value a step ago in time."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

import sympy as sp

from ..circuit.time import TIME, D, Pre
from .expressions import replace


@dataclass(frozen=True)
class DC: ...


@dataclass(frozen=True)
class AC:
    omega: sp.Expr


@dataclass(frozen=True)
class Step:
    dt: sp.Expr


Analysis = DC | AC | Step


def before(x: sp.Expr) -> sp.Symbol:
    """``x`` a step ago: what a step in time remembers."""
    return sp.Symbol(f"{x}⁻")


def is_before(x: sp.Symbol) -> bool:
    return x.name.endswith("⁻")


def interpret(law: sp.Expr, analysis: Analysis) -> sp.Expr:
    match analysis:
        case DC():
            return _reading(law, lambda x: sp.Integer(0), lambda x: x)
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
