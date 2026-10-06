"""What the page asks of a circuit beyond one frame, each a few lines over ``solve``: its frequency response,
a value swept, the spread over builds, the simplest element where a hole is, the resistance between two
points. Each solves once with a letter where a number will go, then only numbers."""

from __future__ import annotations

import cmath
import math
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import cast

import sympy as sp
from electro import (
    AC,
    CurrentSource,
    Element,
    Open,
    Parameter,
    Problem,
    Resistor,
    Solution,
    U,
    Undetermined,
    VoltageSource,
    Wire,
    solve,
)
from electro.circuit.tree import Circuit, Net, Node, Seq, Tensor
from electro.problem.problem import Key
from electro.problem.quantities import Quantity
from electro.values import parse

HALF_POWER_DB = 3.0103


@dataclass(frozen=True)
class Response:
    """``H``: each quantity at each frequency ``f`` (Hz), the source at 1."""

    f: tuple[float, ...]
    H: tuple[complex, ...]

    @property
    def gain_db(self) -> tuple[float, ...]:
        return tuple(20 * math.log10(max(abs(h), 1e-300)) for h in self.H)

    @property
    def phase_deg(self) -> tuple[float, ...]:
        """Unwrapped: no jump of 360° where the phase passes −180°."""
        out: list[float] = []
        for h in self.H:
            p = math.degrees(cmath.phase(h))
            out.append(p + 360 * round((out[-1] - p) / 360) if out else p)
        return tuple(out)

    def cutoffs(self) -> list[float]:
        """Where the gain crosses 3 dB under its largest, straight in log f between two points."""
        g = self.gain_db
        level = max(g) - HALF_POWER_DB
        return [_crossing(self.f, g, k, level) for k in range(len(g) - 1) if (g[k] - level) * (g[k + 1] - level) < 0]


def responses(
    problem: Problem, qs: Sequence[Quantity], source: Element, f: tuple[float, float] = (10, 1e6), points: int = 200
) -> dict[Quantity, Response]:
    """Each of ``qs`` against the frequency, ``source`` at 1: solved once in AC with ω a letter."""
    omega = sp.Symbol("omega", positive=True)
    solution = solve(Problem(problem.circuit, {**problem.given, source: 1}), AC(omega))
    lo, hi = math.log10(f[0]), math.log10(f[1])
    fs = tuple(10 ** (lo + (hi - lo) * k / (points - 1)) for k in range(points))
    out = {}
    for q in qs:
        h = sp.lambdify(omega, solution(q), "cmath")
        out[q] = Response(fs, tuple(complex(h(2 * math.pi * x)) for x in fs))
    return out


def swept(
    problem: Problem, key: Key, values: Sequence[object], qs: Sequence[Quantity], analysis=None
) -> dict[Quantity, tuple[sp.Expr, ...]]:
    """Each of ``qs`` as ``key`` takes each of ``values``: solved once with it a letter."""
    letter = sp.Symbol("swept")
    solution = solve(Problem(problem.circuit, {**problem.given, key: letter}, problem.find), analysis)
    numbers = [cast(sp.Expr, parse(v)) for v in values]
    return {q: tuple(cast(sp.Expr, solution(q).subs(letter, v)) for v in numbers) for q in qs}


def spreads(
    problem: Problem, qs: Sequence[Quantity], tol: float | Mapping[str, float] = 0.05, runs: int = 500, seed: int = 0
) -> dict[Quantity, tuple[float, ...]]:
    """Each of ``qs`` over many builds, every part of a positive value within ``tol`` (the same for all, or by
    kind prefix: ``{"C": 0.1}``): solved once with their values letters."""
    of = {
        e: tol.get(e.kind.prefix, 0.0) if isinstance(tol, Mapping) else tol
        for e in problem.given
        if isinstance(e, Element) and e.kind.positive
    }
    nominal = {e: float(cast(sp.Expr, problem.given[e])) for e, t in of.items() if t}
    letters = {e: sp.Symbol(f"tol_{i}") for i, e in enumerate(nominal)}
    solution = solve(Problem(problem.circuit, {**problem.given, **letters}))
    rng = random.Random(seed)
    builds = [[v * (1 + rng.uniform(-of[e], of[e])) for e, v in nominal.items()] for _ in range(runs)]
    out = {}
    for q in qs:
        f = sp.lambdify(list(letters.values()), solution(q), "cmath")
        out[q] = tuple(amplitude(f(*b)) for b in builds)
    return out


SIMPLEST_FIRST = (Wire, Open, Resistor, VoltageSource, CurrentSource)


@dataclass(frozen=True)
class Filled:
    problem: Problem
    by: Element
    solution: Solution


def fill(problem: Problem, hole: Element, analysis=None) -> Filled:
    """The simplest element where ``hole`` is (``SIMPLEST_FIRST``) that the data neither contradict nor
    leave free."""
    for kind in SIMPLEST_FIRST:
        by = kind(hole.name)
        given = {k: v for k, v in problem.given.items() if k is not hole}
        filled = Problem(_swapped(problem.circuit, hole, by), given, problem.find)
        try:
            solution = solve(filled, analysis)
            for w in by.kind.parameters:
                solution(Parameter(by, w))
        except Undetermined:
            continue
        return Filled(filled, by, solution)
    raise Undetermined("no simple element fits where the hole is")


def resistance(problem: Problem, a: Node | Net, b: Node | Net, analysis=None) -> sp.Expr | None:
    """What the circuit is between ``a`` and ``b`` (an impedance, in AC): how much the voltage there rises per
    ampere let in at ``a`` and out at ``b``."""
    test = CurrentSource("I_test")
    taken = sp.Symbol("I_test")
    try:
        u = solve(Problem(problem.circuit @ (b >> test >> a), {**problem.given, test: taken}), analysis)(U(a, b))
    except Undetermined:
        return None
    z = sp.simplify(sp.diff(u, taken))
    return z if not z.has(taken) else None


def amplitude(v) -> float:
    """A number as a plot shows it: a phasor by its amplitude."""
    z = complex(v)
    return abs(z) if abs(z.imag) > 1e-12 * max(1.0, abs(z)) else z.real


def _swapped(c: Circuit, old: Element, new: Element) -> Circuit:
    match c:
        case Seq(a, b):
            return Seq(_swapped(a, old, new), _swapped(b, old, new))
        case Tensor(a, b):
            return Tensor(_swapped(a, old, new), _swapped(b, old, new))
    return new if c is old else c


def _crossing(f: tuple[float, ...], g: tuple[float, ...], k: int, level: float) -> float:
    t = (level - g[k]) / (g[k + 1] - g[k])
    lo, hi = math.log10(f[k]), math.log10(f[k + 1])
    return 10 ** (lo + t * (hi - lo))
