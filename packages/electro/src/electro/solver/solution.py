"""A solution: the values found, and the steps that found them."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import cast

import sympy as sp

from ..problem.problem import Problem
from ..problem.quantities import Current, Parameter, Power, Quantity, Voltage
from .analysis import DC, Analysis
from .errors import MissingData, Undetermined
from .expressions import subs, symbols_in
from .relation import Origin
from .symbols import Symbols
from .system import parameter_values


@dataclass(frozen=True)
class SolutionStep:
    """What was found, its value, and from which equations (their origins: the reason).

    ``how``: ``"alone"`` (one equation, one unknown), ``"together"`` (several at once), ``"numerically"``,
    ``"assumed"`` (an element taken to be one of its ways), ``"checked"`` (what that way needs holds) or
    ``"rejected"``."""

    found: tuple[sp.Symbol, ...]
    values: tuple[sp.Expr, ...]
    because: tuple[Origin, ...]
    how: str = "alone"
    equations: tuple[sp.Expr, ...] = ()
    """Each origin's equation (= 0), as it was."""


@dataclass(frozen=True)
class Solution:
    """One frame of a circuit: ``unknowns``, what is left not found; ``time``, when (DC: ∞, all settled)."""

    problem: Problem
    values: Mapping[sp.Symbol, sp.Expr]
    unknowns: frozenset[sp.Symbol]
    symbols: Symbols
    worked: tuple[SolutionStep, ...] | Callable[[], tuple[SolutionStep, ...]] = ()
    """The steps, or how to work them out when asked (``steps``)."""
    analysis: Analysis = field(default_factory=DC)
    time: sp.Expr = sp.oo

    def __call__(self, q: Quantity | str) -> sp.Expr:
        """``q``'s value; or by name, ``"I_R_1"``, an expression of names too, ``"U_E_1 / I_E_1"``
        (``problem.names``)."""
        if isinstance(q, str):
            from ..problem.names import evaluated, naming

            return evaluated(q, self, *naming(self.problem.circuit))
        if isinstance(q, Power):
            return sp.simplify(self.analysis.product(self(Voltage(q.of)), self(Current(q.of))))
        value = sp.simplify(self._expression(q))
        if value.free_symbols & self.unknowns:
            raise Undetermined(q)
        return value

    @property
    def steps(self) -> tuple[SolutionStep, ...]:
        """How it is worked out by hand, step by step: each worked out when first asked."""
        if callable(self.worked):
            object.__setattr__(self, "worked", self.worked())
        return cast(tuple[SolutionStep, ...], self.worked)

    def _repr_latex_(self) -> str:
        from ..latex import solution

        return f"${solution(self)}$"

    @property
    def answers(self) -> dict[Quantity, sp.Expr]:
        """What is sought, each found; or ``MissingData``: how many data more, and which would do."""
        found: dict[Quantity, sp.Expr] = {}
        lacking: list[sp.Expr] = []
        targets: list[Quantity] = []
        for q in self.problem.find:
            try:
                found[q] = self(q)
            except Undetermined:
                lacking.append(self._expression(q))
                targets.append(q)
        if not lacking:
            return found
        free = sorted({x for e in lacking for x in symbols_in(e)} & self.unknowns, key=str)
        options = self._pinning(free[0], lacking) if len(free) == 1 else []
        err = MissingData(len(free), options, found, targets)
        err.problem = self.problem
        raise err

    def _expression(self, q: Quantity) -> sp.Expr:
        """``q`` with what was found and what was given in."""
        return self.evaluated(self.symbols.of(q))

    def evaluated(self, e: sp.Expr) -> sp.Expr:
        """``e``, of the circuit's variables, with what was found and what was given in."""
        return subs(subs(e, self.values), parameter_values(self.problem, self.symbols))

    def _pinning(self, x: sp.Symbol, lacking: list[sp.Expr]) -> list[Quantity]:
        """Quantities each of which, given, would pin ``x`` and with it all that is lacking."""
        return [q for q in self._measurable() if self._pins(q, x, lacking)]

    def _pins(self, q: Quantity, x: sp.Symbol, lacking: list[sp.Expr]) -> bool:
        e = self._expression(q)
        if x not in e.free_symbols:
            return False
        roots = sp.solve(e - sp.Dummy("k"), x)
        return len(roots) == 1 and all(not symbols_in(subs(t, {x: roots[0]})) & self.unknowns for t in lacking)

    def _measurable(self) -> list[Quantity]:
        """Each element's parameters, and of a two-terminal one its voltage and current."""
        out: list[Quantity] = []
        for e, _ in self.symbols.net.parts:
            if len(e.kind.terminals) == 2:
                out += [Voltage(e), Current(e)]
            out += [Parameter(e, w) for w in e.kind.parameters]
        return out
