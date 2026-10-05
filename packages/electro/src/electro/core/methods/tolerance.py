"""What a quantity comes to in many builds of a circuit, each part within its tolerance. Solved once with
the varied values as letters, then each build is only numbers."""

from __future__ import annotations

import math
import random
from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

import sympy as sp

from ..circuit.tree import Element
from ..problem.problem import Problem
from ..problem.quantities import Quantity
from ..solver.solve import solve


@dataclass(frozen=True)
class Spread:
    values: tuple[float, ...]

    def stats(self) -> dict[str, float]:
        n = len(self.values)
        mean = sum(self.values) / n
        std = math.sqrt(sum((v - mean) ** 2 for v in self.values) / n)
        return {"mean": mean, "min": min(self.values), "max": max(self.values), "std": std}


def tolerance(
    problem: Problem, q: Quantity, tol: float | Mapping[str, float] = 0.05, runs: int = 500, seed: int = 0
) -> Spread:
    """``tol``: the same for every part of a positive value (a resistor, a capacitor, an inductor), or by
    kind prefix (``{"C": 0.1}``)."""
    tolerances = _tolerances(problem, tol)
    nominal = {e: float(cast(sp.Expr, problem.given[e])) for e in tolerances}
    letters = {e: sp.Symbol(f"tol_{i}") for i, e in enumerate(nominal)}
    at = sp.lambdify(list(letters.values()), solve(Problem(problem.circuit, {**problem.given, **letters}))(q), "math")
    rng = random.Random(seed)

    def build() -> float:
        return float(at(*(v * (1 + rng.uniform(-tolerances[e], tolerances[e])) for e, v in nominal.items())))

    return Spread(tuple(build() for _ in range(runs)))


def _tolerances(problem: Problem, tol: float | Mapping[str, float]) -> dict[Element, float]:
    """Each given part's tolerance, those of none left out."""
    of = {
        e: tol.get(e.kind.prefix, 0.0) if isinstance(tol, Mapping) else tol
        for e in problem.given
        if isinstance(e, Element) and e.kind.positive
    }
    return {e: t for e, t in of.items() if t}
