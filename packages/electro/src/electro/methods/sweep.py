"""What quantities come to as one datum takes each of several values: solved once with that datum a
letter, then each value put in."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import cast

import sympy as sp

from electro.values import parse

from ..problem.problem import Key, Problem
from ..problem.quantities import Quantity
from ..solver.analysis import Analysis
from .ac import solve


@dataclass(frozen=True)
class Sweep:
    values: tuple[sp.Expr, ...]
    results: tuple[sp.Expr, ...]


def sweep(problem: Problem, key: Key, values: Sequence[object], q: Quantity, analysis: Analysis | None = None) -> Sweep:
    return sweeps(problem, key, values, [q], analysis)[q]


def sweeps(
    problem: Problem, key: Key, values: Sequence[object], qs: Sequence[Quantity], analysis: Analysis | None = None
) -> dict[Quantity, Sweep]:
    letter = sp.Symbol("swept")
    solution = solve(Problem(problem.circuit, {**problem.given, key: letter}, problem.find), analysis)
    numbers = tuple(cast(sp.Expr, parse(v)) for v in values)
    return {q: Sweep(numbers, tuple(cast(sp.Expr, solution(q).subs(letter, v)) for v in numbers)) for q in qs}
