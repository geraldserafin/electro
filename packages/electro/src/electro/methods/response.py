"""A frequency response (Bode): a quantity against the frequency, its source at 1 — the transfer function
H, solved once with ω a letter, then only numbers."""

from __future__ import annotations

import cmath
import math
from collections.abc import Sequence
from dataclasses import dataclass

import sympy as sp

from ..circuit.tree import Element
from ..problem.problem import Problem
from ..problem.quantities import Quantity
from ..solver.solve import solve
from .ac import AC

HALF_POWER_DB = 3.0103


@dataclass(frozen=True)
class Response:
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


def respond(
    problem: Problem, q: Quantity, source: Element, f: tuple[float, float] = (10, 1e6), points: int = 200
) -> Response:
    return responses(problem, [q], source, f, points)[q]


def responses(
    problem: Problem, qs: Sequence[Quantity], source: Element, f: tuple[float, float] = (10, 1e6), points: int = 200
) -> dict[Quantity, Response]:
    """Each of ``qs``, from one solution."""
    omega = sp.Symbol("omega", positive=True)
    solution = solve(Problem(problem.circuit, {**problem.given, source: 1}), AC(omega))
    fs = _logarithmic(f, points)
    out = {}
    for q in qs:
        h = sp.lambdify(omega, solution(q), "cmath")
        out[q] = Response(fs, tuple(complex(h(2 * math.pi * x)) for x in fs))
    return out


def _logarithmic(f: tuple[float, float], points: int) -> tuple[float, ...]:
    lo, hi = math.log10(f[0]), math.log10(f[1])
    return tuple(10 ** (lo + (hi - lo) * k / (points - 1)) for k in range(points))


def _crossing(f: tuple[float, ...], g: tuple[float, ...], k: int, level: float) -> float:
    t = (level - g[k]) / (g[k + 1] - g[k])
    lo, hi = math.log10(f[k]), math.log10(f[k + 1])
    return 10 ** (lo + t * (hi - lo))
