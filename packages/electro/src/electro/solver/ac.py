"""AC: frames forever under sines of one angular frequency ω. The circuit never settles, but each frame is
the one before turned by ω·dt — a phasor, ``x⁻ = x·e^(−jω·dt)`` — infinitely many, infinitely short. So
``D`` comes out jω and ``Pre`` the value itself, found by the solver's own limit, not told; a sine in time is
its phasor, and a power the average over a period."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import sympy as sp

from ..circuit.time import TIME
from ..problem.problem import Problem
from . import solve as solver
from .analysis import DC, DT, Step
from .solution import Solution
from .system import equations


@dataclass(frozen=True, init=False)
class AC(Step):
    """At the angular frequency ``omega`` (a number is read as one: ``AC(2 * math.pi * 50)``); its frames
    infinitely short."""

    omega: sp.Expr

    def __init__(self, omega: object) -> None:
        object.__setattr__(self, "dt", sp.Integer(0))
        object.__setattr__(self, "omega", sp.sympify(omega))

    def ago(self, x: sp.Expr) -> sp.Expr:
        return x * sp.exp(-sp.I * self.omega * DT)

    def timed(self, law: sp.Expr) -> sp.Expr:
        return phasors(law, self.omega)

    def product(self, a: sp.Expr, b: sp.Expr) -> sp.Expr:
        """Of phasors: ½·Re(a·b*), the average over a period."""
        return sp.re(sp.expand(a * sp.conjugate(b), complex=True)) / 2


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


def settled(problem: Problem) -> Step:
    """How the circuit settles: with sines in time of one frequency, turning at it (``AC``); else DC."""
    found = {w for eq in equations(problem, DC()).equations for w in frequencies(eq.expr)}
    return AC(found.pop()) if len(found) == 1 else DC()


def frequencies(law: sp.Expr) -> set[sp.Expr]:
    """The angular frequencies of the sines in time in ``law``."""
    return {sp.diff(e.args[0], TIME) for e in law.atoms(sp.sin, sp.cos) if TIME in e.free_symbols}


def solve(problem: Problem, analysis: Step | None = None, before: Solution | None = None) -> Solution:
    """The solver's frame, by default the one the circuit comes to after frames without end (``settled``):
    DC, or with sines of one frequency AC at it."""
    return solver.solve(problem, analysis or settled(problem), before)
