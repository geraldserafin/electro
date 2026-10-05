"""A circuit in time: step by step, each step the equations of ``Step(dt)`` with the state before in
them, compiled once for each way of its elements."""

from __future__ import annotations

import itertools
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from functools import cache

import sympy as sp

from ..circuit.time import TIME, D, Pre
from ..problem.problem import Problem
from ..problem.quantities import Quantity
from .analysis import Step, before
from .errors import NoConvergence, Undetermined
from .expressions import expr, subs, symbols_in
from .newton import Jacobian, Residual, compiled, homotopy, newton
from .relation import Relation, all_equations
from .symbols import Symbols, symbols
from .system import SOURCES, equations, relation


@dataclass(frozen=True)
class State:
    """``values``: every unknown at ``t``; ``way``: which combination of its elements' ways it was in."""

    t: float
    values: Mapping[sp.Symbol, float]
    way: int = 0


@dataclass(frozen=True)
class Stepper:
    """One step, for one way of the elements, compiled. ``holds``: what that way needs (≥ 0)."""

    unknowns: tuple[sp.Symbol, ...]
    f: Residual = field(repr=False)
    j: Jacobian = field(repr=False)
    holds: tuple[sp.Expr, ...]


@dataclass(frozen=True)
class Stepping:
    """``remembered``: what each value a step ago is; ``stepper(k)`` for each of ``ways`` combinations,
    compiled when first needed."""

    dt: float
    remembered: tuple[sp.Expr, ...]
    ways: int
    stepper: Callable[[int], Stepper] = field(repr=False)


@dataclass(frozen=True)
class Trace:
    problem: Problem
    states: tuple[State, ...]
    symbols: Symbols

    def __call__(self, q: Quantity) -> Callable[[float], float]:
        """``q`` in time: a function of t, the nearest step's value."""
        x = self.symbols.of(q)
        ys = [float(subs(x, s.values)) for s in self.states]

        def at(t: float) -> float:
            return ys[min(range(len(self.states)), key=lambda i: abs(self.states[i].t - t))]

        return at


def simulate(problem: Problem, until: float, dt: float | None = None) -> Trace:
    """From rest (every capacitor empty, every inductor still) for ``until`` seconds."""
    stepping = compile_steps(problem, dt or until / 1000)
    states = [State(0.0, {})]
    while states[-1].t < until - 1e-12:
        states.append(step(stepping, states[-1]))
    return Trace(problem, tuple(states[1:]), symbols(problem.circuit))


def compile_steps(problem: Problem, dt: float) -> Stepping:
    system = equations(problem, Step(sp.Float(dt)), sources=SOURCES)
    remembered = _remembered(relation(problem.circuit))
    previous = [before(x) for x in remembered]
    combinations = list(itertools.product(*system.choices))

    @cache
    def stepper(k: int) -> Stepper:
        ways = combinations[k]
        exprs = [eq.expr for eq in system.equations] + [eq.expr for w in ways for eq in w.equations]
        unknowns = [u for u in system.unknowns if u not in previous]
        if any(x not in {*unknowns, SOURCES, TIME, *previous} for e in exprs for x in symbols_in(e)):
            raise Undetermined("a step in time needs every value")
        f, j = compiled(exprs, unknowns, (SOURCES, TIME, *previous))
        return Stepper(tuple(unknowns), f, j, tuple(h for w in ways for h in w.holds))

    return Stepping(dt, tuple(remembered), len(combinations), stepper)


def step(stepping: Stepping, state: State) -> State:
    """``dt`` on: in the way it was if that still holds, else the next way that does."""
    now = state.t + stepping.dt
    at = {**dict.fromkeys(stepping.stepper(state.way).unknowns, 0.0), **state.values}
    prev = [float(subs(x, at)) for x in stepping.remembered]
    remembered = dict(zip(map(before, stepping.remembered), prev))
    for k in (state.way, *(k for k in range(stepping.ways) if k != state.way)):
        s = stepping.stepper(k)
        x = _settle(s, [at.get(u, 0.0) for u in s.unknowns], now, prev)
        if x is None:
            continue
        values = dict(zip(s.unknowns, x))
        if all(float(subs(h, {**values, TIME: now, **remembered})) >= -1e-9 for h in s.holds):
            return State(now, values, k)
    raise NoConvergence(now)


def _remembered(rel: Relation) -> list[sp.Expr]:
    """What a step remembers: each quantity under ``D`` or ``Pre``."""
    held = {expr(a.args[0]) for eq in all_equations(rel) for a in eq.expr.atoms(D, Pre)}
    return sorted(held, key=str)


def _settle(s: Stepper, guess: Sequence[float], now: float, prev: Sequence[float]) -> list[float] | None:
    """Newton from the last state; undamped across a jump (logic); the sources raised as a last resort."""
    found = newton(s.f, s.j, guess, (1.0, now, *prev))
    if found is None:
        found = newton(s.f, s.j, guess, (1.0, now, *prev), damped=False)
    if found is None:
        found = homotopy(s.f, s.j, len(guess), (now, *prev), guess)
    return found
