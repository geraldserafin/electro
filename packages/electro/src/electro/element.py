"""An element: a kind's terminals and its laws between them — a circuit of one element. A kind (``Resistor``)
is a subclass that says its terminals and its laws; nothing else.

Its laws are equations, with no direction: on each terminal's potential ``V`` and the current ``I`` into the
element there, its parameters ``P`` and its inner quantities, in the words of time (``D``, ``Pre``) where it
remembers. An element of several ways (the textbook's diode, on or off) says each way's laws and what must
hold for it to be that way."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

import sympy as sp

from .circuit import Circuit, Point
from .errors import BadName


@dataclass(frozen=True)
class Origin:
    """Why an equation holds, the reason a step gives: ``what`` is ``"law"`` (an element's ``index``-th;
    ``case``: the way it then is), ``"kcl"`` (Kirchhoff at a point), ``"given"`` (a datum), ``"reference"`` (a
    potential chosen 0), ``"assumed"`` or ``"holds"``; ``subject``: the element, the point, the datum's key."""

    what: str
    subject: object
    index: int = 0
    case: str = ""


@dataclass(frozen=True)
class Equation:
    """``expr`` = 0, and why."""

    expr: sp.Expr
    origin: Origin


@dataclass(frozen=True)
class SolutionStep:
    """What a frame found, its value, and from which equations (their origins: the reason). ``how``:
    ``"alone"`` (one equation, one unknown), ``"together"`` (several at once), ``"numerically"``, ``"assumed"``
    (an element taken to be one of its ways), ``"checked"`` (what that way needs holds) or ``"rejected"``."""

    found: tuple[sp.Symbol, ...]
    values: tuple[sp.Expr, ...]
    because: tuple[Origin, ...]
    how: str = "alone"
    equations: tuple[sp.Expr, ...] = ()
    """Each origin's equation (= 0), as it was."""


@dataclass(frozen=True)
class Case:
    """One way an element may be (a diode on, or off): its laws then, and what must hold for it to be that
    way, each ``holds`` ≥ 0."""

    name: str
    laws: tuple[sp.Expr, ...]
    holds: tuple[sp.Expr, ...] = ()


@dataclass(frozen=True)
class Cases:
    """An element of several ways: the frame decides which — the one whose ``holds`` hold."""

    cases: tuple[Case, ...]


@dataclass(frozen=True)
class Way:
    """One way an element may be: its equations then, and what must hold (≥ 0)."""

    element: object
    name: str
    equations: tuple[Equation, ...]
    holds: tuple[sp.Expr, ...]


@dataclass(frozen=True)
class Terminals:
    """What a kind's laws speak of: each terminal's potential ``V`` and the current ``I`` into the element
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
    """A kind of element says, as class attributes, ``terminals``, ``parameters`` (``""`` its main one, given
    as its value), ``defaults``, ``positive`` (never negative: a resistance), ``inputs`` (set by the world while
    it runs: a hand on a switch), ``shows`` (what a page reads of it besides its currents), ``ground`` (its last
    terminal, not drawn, on ground), ``kind`` and ``prefix`` (its name and its label's letters); and ``laws``.
    Of two terminals it is 1 → 1, of more 0 → n."""

    kind = "element"
    prefix = "X"
    terminals: tuple[str, ...] = ()
    parameters: tuple[str, ...] = ("",)
    defaults: Mapping[str, object] = {}
    positive: tuple[str, ...] = ()
    inputs: tuple[str, ...] = ()
    shows: tuple[tuple[str, tuple[str, str] | str], ...] = ()
    ground = False

    def laws(self, t: Terminals, p: Params) -> Sequence[sp.Expr] | Cases:  # type: ignore[override]
        raise NotImplementedError(type(self).__name__)

    def __init__(self, name: str | None = None) -> None:
        if name is not None and not name.isidentifier():
            raise BadName(name)
        self.name = name
        ts = self.terminals
        self.V = {t: sp.Integer(0) if self.ground and t == ts[-1] else sp.Dummy(f"v_{t}") for t in ts}
        own = {t: sp.Dummy(f"i_{t}") for t in ts[:-1]}
        self.I = {**own, ts[-1]: -sp.Add(*own.values())} if ts else {}
        self.P = {w: sp.Symbol(f"{w}_{name}" if w else name) if name else sp.Dummy(w or "p") for w in self.parameters}
        self.inner: dict[str, sp.Symbol] = {}
        said = self.laws(Terminals(self.V, self.I, self._inner), self.P)
        cases = said.cases if isinstance(said, Cases) else (Case("", tuple(said)),)

        def equations(case: Case) -> tuple[Equation, ...]:
            return tuple(
                Equation(sp.sympify(law), Origin("law", self, i, case.name)) for i, law in enumerate(case.laws)
            )

        several = len(cases) > 1
        self.equations = () if several else equations(cases[0])
        self.ways = (
            tuple(Way(self, c.name, equations(c), tuple(map(sp.sympify, c.holds))) for c in cases) if several else ()
        )
        at = tuple(Point(self.V[t]) for t in self.drawn)
        ends = (at[:1], at[1:]) if len(ts) == 2 else ((), at)
        Circuit.__init__(self, ((self, at),), *ends)

    @property
    def drawn(self) -> tuple[str, ...]:
        """Its terminals that are drawn: all but the one on ground."""
        return self.terminals[:-1] if self.ground else self.terminals

    def _inner(self, name: str) -> sp.Symbol:
        return self.inner.setdefault(name, sp.Dummy(name))

    def setting(self, which: str, value: object) -> dict[str, float]:
        """What the world sets, setting ``which`` to ``value``: its inputs by name (a hand on a switch: one)."""
        return {which: float(value)}  # type: ignore[arg-type]

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.name!r})" if self.name else type(self).__name__ + "()"
