"""An element is a circuit of one element. A kind of element (``Resistor``) is a subclass that says its
terminals and its laws; nothing else.

Its laws are equations, with no direction, on: each terminal's potential ``V`` and the current ``I`` into the
element there, its parameters ``P`` and its inner quantities; ``D`` and ``Pre`` where it remembers. An element of
several ways (the textbook's diode, on or off) gives ``Cases``: each way's laws and what must hold for it."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

import sympy as sp

from .circuit import Circuit, Point
from .errors import BadName
from .laws import Equation, Origin, Way


@dataclass(frozen=True)
class Case:
    """One way an element may be: its laws then, and what must hold for it (each of ``holds`` ≥ 0)."""

    name: str
    laws: tuple[sp.Expr, ...]
    holds: tuple[sp.Expr, ...] = ()


@dataclass(frozen=True)
class Cases:
    """An element of several ways; the circuit decides which one it is."""

    cases: tuple[Case, ...]


@dataclass(frozen=True)
class Terminals:
    """What a kind's laws are written in: each terminal's potential ``V`` and the current ``I`` into the element
    there, and its inner quantities by name."""

    V: Mapping[str, sp.Expr]
    I: Mapping[str, sp.Expr]
    inner: Callable[[str], sp.Symbol]

    def across(self, a: str, b: str) -> sp.Expr:
        """V_a − V_b."""
        return self.V[a] - self.V[b]


Params = Mapping[str, sp.Expr]
"""An element's parameters by name; ``""`` is its main one (R, C, E)."""


class Element(Circuit):
    """A kind says, as class attributes: ``terminals``; ``parameters`` (``""`` the main one, given as its value),
    ``defaults``, ``positive`` (never negative, like a resistance); ``inputs`` (set from outside while it runs,
    like a switch); ``shows`` (what a page reads of it besides its currents); ``ground`` (its last terminal is
    not drawn and is on ground); ``kind`` and ``prefix`` (its name and its label's letters); and ``laws``. With
    two terminals it is 1 → 1, with more 0 → n."""

    kind = "element"
    prefix = "X"
    terminals: tuple[str, ...] = ()
    parameters: tuple[str, ...] = ("",)
    defaults: Mapping[str, object] = {}
    positive: tuple[str, ...] = ()
    inputs: tuple[str, ...] = ()
    shows: tuple[tuple[str, tuple[str, str] | str], ...] = ()
    ground = False

    def laws(self, t: Terminals, p: Params) -> Sequence[sp.Expr] | Cases:
        raise NotImplementedError(type(self).__name__)

    def __init__(self, name: str | None = None) -> None:
        if name is not None and not name.isidentifier():
            raise BadName(name)
        self.name = name
        self.V, self.I, self.P = self._potentials(), self._currents(), self._parameters()
        self.inner: dict[str, sp.Symbol] = {}
        cases = self._cases()
        self.equations = self._equations(cases[0]) if len(cases) == 1 else ()
        self.ways = tuple(self._way(c) for c in cases) if len(cases) > 1 else ()
        Circuit.__init__(self, *self._drawing())

    @property
    def drawn(self) -> tuple[str, ...]:
        """Its terminals that are drawn: all but the one on ground."""
        return self.terminals[:-1] if self.ground else self.terminals

    def setting(self, which: str, value: object) -> dict[str, float]:
        """What setting ``which`` to ``value`` from outside sets: its inputs by name (a switch: one)."""
        return {which: float(value)}  # type: ignore[arg-type]

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.name!r})" if self.name else type(self).__name__ + "()"

    # What its laws are written in

    def _potentials(self) -> dict[str, sp.Expr]:
        return {t: sp.Dummy(f"v_{t}") if t in self.drawn else sp.Integer(0) for t in self.terminals}

    def _currents(self) -> dict[str, sp.Expr]:
        """One current into each terminal but the last; into the last, what the others bring."""
        if not self.terminals:
            return {}
        *ts, last = self.terminals
        own = {t: sp.Dummy(f"i_{t}") for t in ts}
        return {**own, last: -sp.Add(*own.values())}

    def _parameters(self) -> dict[str, sp.Symbol]:
        """A named element's parameters are named after it (elements named alike share them)."""
        name = self.name
        return {w: sp.Symbol(f"{w}_{name}" if w else name) if name else sp.Dummy(w or "p") for w in self.parameters}

    def _inner(self, name: str) -> sp.Symbol:
        return self.inner.setdefault(name, sp.Dummy(name))

    # Its laws

    def _cases(self) -> tuple[Case, ...]:
        said = self.laws(Terminals(self.V, self.I, self._inner), self.P)
        return said.cases if isinstance(said, Cases) else (Case("", tuple(said)),)

    def _equations(self, case: Case) -> tuple[Equation, ...]:
        return tuple(Equation(sp.sympify(law), Origin("law", self, i, case.name)) for i, law in enumerate(case.laws))

    def _way(self, case: Case) -> Way:
        return Way(self, case.name, self._equations(case), tuple(map(sp.sympify, case.holds)))

    def _drawing(self) -> tuple:
        """A point for each drawn terminal: 1 → 1 with two terminals, else 0 → n."""
        at = tuple(Point(self.V[t]) for t in self.drawn)
        ends = (at[:1], at[1:]) if len(self.terminals) == 2 else ((), at)
        return ((self, at),), *ends
