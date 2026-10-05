"""The analyses. Each reads a law's time words its own way: ``D`` is 0 in DC, jω in AC, the difference
back over a step in time; ``Pre`` is the value itself in DC and AC, the value a step ago in time."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import sympy as sp

from ..circuit.time import D, Pre
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
