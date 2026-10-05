"""What a quantity comes to as one datum takes each of several values."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import cast

import sympy as sp

from electro.values import parse

from ..problem.problem import Key, Problem
from ..problem.quantities import Quantity
from ..solver.analysis import AC, DC
from ..solver.solve import solve


@dataclass(frozen=True)
class Sweep:
    values: tuple[sp.Expr, ...]
    results: tuple[sp.Expr, ...]


def sweep(problem: Problem, key: Key, values: Sequence[object], q: Quantity, analysis: DC | AC | None = None) -> Sweep:
    results = tuple(
        solve(Problem(problem.circuit, {**problem.given, key: v}, problem.find), analysis)(q) for v in values
    )
    return Sweep(tuple(cast(sp.Expr, parse(v)) for v in values), results)
