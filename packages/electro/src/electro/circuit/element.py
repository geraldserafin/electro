"""Element: anything with ends and laws between them. A resistor is one; so is ``E >> R``, and every circuit.

An element is a relation of its ends (``Rel``) — at each a potential and a current (in at a left end, out at
a right one) — and its laws (``Laws``) say what holds between them, in the words of time (``D``, ``Pre``)
where it remembers. A kind of element (``Resistor``) is a subclass that says its terminals and its laws;
nothing else.

Relations are the morphisms of a hypergraph category, and every way of joining is one of its operations:

- ``f @ g``: side by side — the ends side by side, both laws hold (``&``);
- ``f >> g``: ``f``'s right ends are ``g``'s left ends — each pair of variables made one (a pushout: one
  goes, logged as a wire's), then what is inside hidden (∃: ``Laws.eliminate``). ``R_1 >> R_2`` so comes to
  one law of its ends, ``U = (R_1 + R_2)·I``, with nothing told of series;
- ``f | g``, ``~f``, ``-f``: ``>>`` and ``@`` with points (``points``).

A variable inside goes by an equation of degree one in it whose factor holds no variable, is never zero as
the circuit runs, and is not under a function (``exp``, a time word): what is tangled stays, for Newton.
Nothing here knows any kind of element.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

import sympy as sp

from .algebra import JOINING, Cases, Equation, Laws, Origin, SolutionStep, Way, linear, symbols_in, ways
from .time import TIME, D, Pre


class BadName(ValueError):
    """A name with more than letters, digits and ``_``: nothing else reaches the equations or the code."""

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.name = name


class ElementTwice(ValueError):
    """One element in two places: two elements are two objects (``Resistor("R")`` twice)."""


class JoinsNodes(ValueError):
    """``>>`` would glue two different named points into one: say it with the same ``Node`` instead."""


class WrongEnds(ValueError):
    """``>>`` of pieces whose ends do not meet: ``left`` ends into ``right``."""

    def __init__(self, left: int, right: int) -> None:
        super().__init__(left, right)
        self.left, self.right = left, right


POTENTIALS: set[sp.Symbol] = set()
"""Every terminal's and named point's potential: what a reference (``formula``) is chosen among."""

NAMED: set[sp.Symbol] = set()
"""A named point's potential: one variable wherever the point is, never gone inside an element."""

PARAMETERS: set[sp.Symbol] = set()
"""An unnamed element's parameters: given, never gone by joining."""


@dataclass(frozen=True)
class End:
    v: sp.Expr
    i: sp.Expr


@dataclass(frozen=True)
class Rel:
    """A relation of ends: its ``left`` and ``right`` ends, its ``laws``, and the current into each named
    point from it (``taps``: Kirchhoff there waits for the circuit to be whole)."""

    left: tuple[End, ...] = ()
    right: tuple[End, ...] = ()
    laws: Laws = Laws()
    taps: tuple[tuple[object, sp.Expr], ...] = ()

    def map(self, f: Callable[[sp.Expr], sp.Expr]) -> Rel:
        def end(e: End) -> End:
            return End(f(e.v), f(e.i))

        return Rel(
            tuple(map(end, self.left)),
            tuple(map(end, self.right)),
            self.laws.map(f),
            tuple((p, f(i)) for p, i in self.taps),
        )

    def __matmul__(self, other: Rel) -> Rel:
        return Rel(self.left + other.left, self.right + other.right, self.laws & other.laws, self.taps + other.taps)

    def __rshift__(self, other: Rel) -> Rel:
        if len(self.right) != len(other.left):
            raise WrongEnds(len(self.right), len(other.left))
        r = Rel(self.left, other.right, self.laws & other.laws, self.taps + other.taps)
        for x, y in zip(self.right, other.left):
            for a, b in ((x.v, y.v), (x.i, y.i)):
                r = r.glued(a, b)
        return r.hidden()

    def glued(self, a: sp.Expr, b: sp.Expr) -> Rel:
        """``a`` and ``b`` one: a variable that may go goes (what only joins first, else ``b``), logged as a
        wire's; two that may not, a wire's equation."""
        a, b = self.laws.resolve(a), self.laws.resolve(b)
        if sp.expand(a - b) == 0:
            return self
        if _named(a) and _named(b):
            raise JoinsNodes(a, b)
        goes = [x for x in (b, a) if isinstance(x, sp.Symbol) and not _named(x)]
        wire = Origin("wire", None)
        if not goes:
            return Rel(self.left, self.right, self.laws & Laws((Equation(a - b, wire),)), self.taps)
        x = min(goes, key=lambda x: x not in JOINING)
        value = a if x == b else b
        r = self.map(lambda e: e.xreplace({x: value}) if e.has(x) else e)
        return Rel(
            r.left, r.right, r.laws & Laws(log=(SolutionStep((x,), (value,), (wire,), equations=(x - value,)),)), r.taps
        )

    def hidden(self) -> Rel:
        """What is inside gone where it can: every variable but those on its ends, the named points', and the
        parameters."""
        ends = {x for e in (*self.left, *self.right) for x in (*symbols_in(e.v), *symbols_in(e.i))}
        inside = {
            x
            for q in (*self.laws.equations, *(q for c in self.laws.choices for w in c for q in w.equations))
            for x in symbols_in(q.expr)
            if isinstance(x, sp.Dummy) and x not in NAMED and x not in PARAMETERS
        }
        laws = self.laws.eliminate(inside - ends, linear(inside | NAMED, _steady), keep=ends)
        new = Laws(log=laws.log[len(self.laws.log) :])
        return Rel(self.left, self.right, laws, tuple((p, new.resolve(i)) for p, i in self.taps))

    @property
    def wires(self) -> tuple[tuple[sp.Symbol, sp.Expr], ...]:
        """Which variables joining made one: what a drawing of it needs (which terminals are one point)."""
        return tuple((s.found[0], s.values[0]) for s in self.laws.log if s.because[0].what == "wire" and s.found)


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


class Element:
    """A kind of element says, as class attributes, ``terminals``, ``parameters`` (``""`` its main one, given
    as its value), ``defaults``, ``positive`` (never negative: a resistance), ``inputs`` (set by the world while
    it runs: a hand on a switch), ``shows`` (what a page reads of it besides its currents: a voltage between
    two terminals, or a current into one, by name), ``modes`` (a board pin's ways), ``ground`` (its last
    terminal, not drawn, on ground: one end fewer), ``kind`` and ``prefix`` (its name and its label's
    letters); and ``laws``. An element of two terminals is 1 → 1, of more 0 → n."""

    kind = "element"
    prefix = "X"
    terminals: tuple[str, ...] = ()
    parameters: tuple[str, ...] = ("",)
    defaults: Mapping[str, object] = {}
    positive: tuple[str, ...] = ()
    inputs: tuple[str, ...] = ()
    shows: tuple[tuple[str, tuple[str, str] | str], ...] = ()
    modes: Mapping[str, tuple[float, float]] = {}
    ground = False

    name: str | None
    rel: Rel
    members: tuple[Element, ...]
    """The kinds' elements it is made of, in order."""

    def laws(self, t: Terminals, p: Params) -> Sequence[sp.Expr] | Cases:
        raise NotImplementedError(type(self).__name__)

    def __init__(self, name: str | None = None) -> None:
        if name is not None and not name.isidentifier():
            raise BadName(name)
        self.name = name
        ts = self.terminals
        self.V = {t: sp.Integer(0) if self.ground and t == ts[-1] else sp.Dummy(f"v_{t}") for t in ts}
        POTENTIALS.update(v for v in self.V.values() if isinstance(v, sp.Symbol))
        own = {t: sp.Dummy(f"i_{t}") for t in ts[:-1]}
        self.I = {**own, ts[-1]: -sp.Add(*own.values())} if ts else {}
        self.P = {w: _parameter(name, w) for w in self.parameters}
        self.inner: dict[str, sp.Symbol] = {}
        cases = ways(self.laws(Terminals(self.V, self.I, self._inner), self.P))

        def equations(case) -> tuple[Equation, ...]:
            return tuple(Equation(law, Origin("law", self, i, case.name)) for i, law in enumerate(case.laws))

        laws = (
            Laws(equations(cases[0]))
            if len(cases) == 1
            else Laws(choices=(tuple(Way(self, c.name, equations(c), c.holds) for c in cases),))
        )
        if len(ts) == 2:
            ends = ((End(self.V[ts[0]], self.I[ts[0]]),), (End(self.V[ts[1]], -self.I[ts[1]]),))
        else:
            ends = ((), tuple(End(self.V[t], -self.I[t]) for t in (ts[:-1] if self.ground else ts)))
        self.rel = Rel(*ends, laws)
        self.members = (self,)

    def _inner(self, name: str) -> sp.Symbol:
        return self.inner.setdefault(name, sp.Dummy(name))

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.name!r})" if self.name else type(self).__name__ + "()"

    # Joining

    def piece(self) -> Rel:
        """Its relation where it is used: an element is one object, in one place; what only joins (points,
        crossings and what is made of them) is fresh wherever it is used."""
        r = self.rel
        if self.members:
            return r
        fresh = {x: sp.Dummy(x.name) for x in _variables(r) if x not in NAMED}
        JOINING.update(fresh.values())
        POTENTIALS.update(y for x, y in fresh.items() if x in POTENTIALS)
        return r.map(lambda e: e.xreplace(fresh))

    def __rshift__(self, other: Element) -> Element:
        return composite(self.piece() >> other.piece(), _members(self, other))

    def __matmul__(self, other: Element) -> Element:
        return composite(self.piece() @ other.piece(), _members(self, other))

    def __or__(self, other: Element) -> Element:
        from .points import Spider

        return Spider(1, 2) >> (self @ other) >> Spider(2, 1)

    def __invert__(self) -> Element:
        from .points import Spider

        return Spider(0, 2) >> (self @ Spider(1, 1)) >> Spider(2, 0)

    def __neg__(self) -> Element:
        from .points import Spider

        wire = Spider(1, 1)
        return (wire @ Spider(0, 2)) >> (wire @ self @ wire) >> (Spider(2, 0) @ wire)

    # What it says

    @property
    def free(self) -> tuple[int, int]:
        """How many of its ends, left and right, are not on a named point: still to be joined."""
        return sum(not _named(e.v) for e in self.rel.left), sum(not _named(e.v) for e in self.rel.right)

    def __str__(self) -> str:
        """A 1 → 1 element as a book writes it: its voltage ``U`` (the first end against the second) by its
        current ``I`` (in at the first) — ``U = I·(R_1 + R_2)``; else its laws."""
        return said(self.rel)

    # Its frames: where it ends, and in time

    def final(self, values: Mapping | None = None, frame=None):
        """Where the circuit comes to: one frame infinitely long — or, with sines of one frequency, turning at
        it — from rest, its values in."""
        from ..solve.final import final

        return final(self, values or {}, frame)

    def simulate(self, values: Mapping | None = None, until: float = 1.0, dt: float | None = None, inputs=None):
        """Frame after frame from rest for ``until`` seconds."""
        from ..simulate import simulate

        return simulate(self, values or {}, until, dt, inputs)


def _named(v: sp.Expr) -> bool:
    return v == 0 or v in NAMED


def _variables(r: Rel) -> set[sp.Symbol]:
    out: set[sp.Symbol] = set()
    r.map(lambda e: out.update(x for x in symbols_in(e) if isinstance(x, sp.Dummy)) or e)
    return out


def composite(rel: Rel, members: tuple[Element, ...]) -> Element:
    """An element made of others: no kind of its own, its relation what joining them left."""
    e = object.__new__(Element)
    e.name, e.rel, e.members = None, rel, members
    return e


def _parameter(name: str | None, which: str) -> sp.Symbol:
    """A named element's parameter is its name (elements named alike share it); an unnamed one's its own."""
    if name:
        return sp.Symbol(f"{which}_{name}" if which else name)
    p = sp.Dummy(which or "p")
    PARAMETERS.add(p)
    return p


def _members(a: Element, b: Element) -> tuple[Element, ...]:
    both = a.members + b.members
    if len({id(e) for e in both}) != len(both):
        raise ElementTwice(next(e for e in both if both.count(e) > 1).name or "an element")
    return both


def _steady(a: sp.Expr) -> bool:
    """A factor that is never 0 as the circuit runs: no function in it (a state, a switch: 0 one moment), nor
    a time word."""
    return not a.atoms(sp.Function) and not a.has(TIME, D, Pre)


def said(r: Rel) -> str:
    """A relation of one end each side as ``U = …`` (or ``I = …``): its laws and ``U``, ``I`` at its ends,
    all else hidden."""
    if len(r.left) == len(r.right) == 1 and not r.laws.choices:
        U, I = sp.symbols("U I")
        (a,), (b,) = r.left, r.right
        eqs = [q.expr for q in r.laws.equations] + [U - (a.v - b.v), I - a.i]
        inside = sorted({x for e in eqs for x in symbols_in(e) if isinstance(x, sp.Dummy)}, key=str)
        for x in (U, I):
            try:
                found = sp.solve(eqs, [*inside, x], dict=True)
            except NotImplementedError:  # under a time word: said as it is, below
                continue
            if len(found) == 1 and x in found[0]:
                return f"{x} = {sp.factor(found[0][x])}"
        plain = [e for e in eqs if not e.atoms(sp.Function)]
        by = sp.solve(plain, [x for x in inside if any(e.has(x) for e in plain)], dict=True)
        if len(by) == 1:
            left = {sp.factor(sp.expand(e.xreplace(by[0]))) for e in eqs} - {0}
            if not {x for e in left for x in symbols_in(e) if isinstance(x, sp.Dummy)}:
                return "; ".join(f"{e} = 0" for e in left)
    return "; ".join(f"{q.expr} = 0" for q in r.laws.equations)
