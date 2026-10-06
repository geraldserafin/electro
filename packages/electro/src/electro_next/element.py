"""Element: anything with ends and laws between them. A resistor is one; so is ``E >> R``, and every circuit.

An element is a relation of its ends — at each a potential and a current (in at a left end, out at a right
one) — and its laws say what holds between them, in the words of time (``D``, ``Pre``) where it remembers.
A kind of element (``Resistor``) is a subclass that says its terminals and its laws; nothing else.

Elements are joined by:

- ``f >> g``: ``f``'s right ends are ``g``'s left ends — and what is then inside goes (∃: composing relations
  hides what two pieces share), its definition kept, still there to be asked (``I(R)``). ``R_1 >> R_2`` so
  comes to one law of its ends, ``U = (R_1 + R_2)·I``, with nothing told of series;
- ``f @ g``: side by side; ``f | g``: both between the same two points; ``~f``: a 1 → 1 element's two ends
  joined (a loop); ``-f``: a 1 → 1 element the other way round.

A variable goes by an equation of degree one in it whose factor holds no variable, is never zero as the
circuit runs, and is not under a function (``exp``, a time word): what is tangled so stays, for Newton. Nothing
here knows any kind of element.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace

import sympy as sp

from .algebra import Cases, Equation, Origin, Way, normal, symbols_in, ways
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


@dataclass(frozen=True)
class End:
    v: sp.Expr
    i: sp.Expr


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


@dataclass(frozen=True)
class Relation:
    """What an element is, seen from outside: its ends, its laws, its elements of several ways, the current
    into each named point from it, what it eliminated (``x = value`` by ``eq``, in order), and which of its
    variables only join (a spider's, a crossing's: fresh wherever the piece is used again)."""

    left: tuple[End, ...] = ()
    right: tuple[End, ...] = ()
    laws: tuple[Equation, ...] = ()
    choices: tuple[tuple[Way, ...], ...] = ()
    taps: tuple[tuple[object, sp.Expr], ...] = ()
    definitions: tuple[tuple[sp.Symbol, sp.Expr, Equation], ...] = ()
    joining: frozenset[sp.Symbol] = frozenset()


POTENTIALS: set[sp.Symbol] = set()
"""Every terminal's and named point's potential: what a reference (``formula``) is chosen among."""

NAMED: set[sp.Symbol] = set()
"""A named point's potential: one variable wherever the point is, never gone inside an element."""

PARAMETERS: set[sp.Symbol] = set()
"""An unnamed element's parameters: given, never gone by joining."""


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
    relation: Relation
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

        laws, choices = (
            (equations(cases[0]), ())
            if len(cases) == 1
            else ((), (tuple(Way(self, c.name, equations(c), c.holds) for c in cases),))
        )
        if len(ts) == 2:
            ends = ((End(self.V[ts[0]], self.I[ts[0]]),), (End(self.V[ts[1]], -self.I[ts[1]]),))
        else:
            ends = ((), tuple(End(self.V[t], -self.I[t]) for t in (ts[:-1] if self.ground else ts)))
        self.relation = Relation(*ends, laws, choices)
        self.members = (self,)

    def _inner(self, name: str) -> sp.Symbol:
        return self.inner.setdefault(name, sp.Dummy(name))

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.name!r})" if self.name else type(self).__name__ + "()"

    # Joining

    def piece(self) -> Relation:
        """Its relation where it is used: what only joins, fresh (an element itself is one object)."""
        r = self.relation
        if not r.joining:
            return r
        fresh = {x: sp.Dummy(x.name) for x in r.joining}
        POTENTIALS.update(y for x, y in fresh.items() if x in POTENTIALS)
        return _renamed(r, fresh, frozenset(fresh.values()))

    def __rshift__(self, other: Element) -> Element:
        a, b = self.piece(), other.piece()
        if len(a.right) != len(b.left):
            raise WrongEnds(len(a.right), len(b.left))
        for x, y in zip(a.right, b.left):
            if _named(x.v) and _named(y.v) and x.v != y.v:
                raise JoinsNodes(x.v, y.v)
        wires = [
            Equation(one - two, Origin("wire", None))
            for x, y in zip(a.right, b.left)
            for one, two in ((x.v, y.v), (x.i, y.i))
            if sp.expand(one - two) != 0
        ]
        both = _beside(a, b)
        glued = replace(both, left=a.left, right=b.right, laws=(*both.laws, *wires))
        return composite(reduced(glued), _members(self, other))

    def __matmul__(self, other: Element) -> Element:
        return composite(_beside(self.piece(), other.piece()), _members(self, other))

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
        on = lambda e: e.v == 0 or e.v in NAMED  # noqa: E731
        return sum(not on(e) for e in self.relation.left), sum(not on(e) for e in self.relation.right)

    def __str__(self) -> str:
        """A 1 → 1 element as a book writes it: its voltage ``U`` (the first end against the second) by its
        current ``I`` (in at the first) — ``U = I·(R_1 + R_2)``; else its laws."""
        return said(self.relation)

    # Its frames (``formula``): where it ends, and in time

    def final(self, values: Mapping | None = None, frame=None):
        """Where the circuit comes to: one frame infinitely long — or, with sines of one frequency, turning at
        it — from rest, its values in."""
        from .solve import final

        return final(self, values or {}, frame)

    def simulate(self, values: Mapping | None = None, until: float = 1.0, dt: float | None = None, inputs=None):
        """Frame after frame from rest for ``until`` seconds."""
        from .simulate import simulate

        return simulate(self, values or {}, until, dt, inputs)


def _named(v: sp.Expr) -> bool:
    return v == 0 or v in NAMED


def composite(relation: Relation, members: tuple[Element, ...]) -> Element:
    """An element made of others: no kind of its own, its relation what joining them left."""
    e = object.__new__(Element)
    e.name, e.relation, e.members = None, relation, members
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


def _beside(a: Relation, b: Relation) -> Relation:
    return Relation(
        a.left + b.left,
        a.right + b.right,
        a.laws + b.laws,
        a.choices + b.choices,
        a.taps + b.taps,
        a.definitions + b.definitions,
        a.joining | b.joining,
    )


def _renamed(r: Relation, to: Mapping[sp.Symbol, sp.Expr], joining: frozenset) -> Relation:
    def ren(e: sp.Expr) -> sp.Expr:
        return e.xreplace(to)

    return Relation(
        tuple(End(ren(e.v), ren(e.i)) for e in r.left),
        tuple(End(ren(e.v), ren(e.i)) for e in r.right),
        tuple(Equation(ren(q.expr), q.origin) for q in r.laws),
        tuple(tuple(_way(w, ren) for w in c) for c in r.choices),
        tuple((p, ren(i)) for p, i in r.taps),
        tuple((to.get(x, x), ren(v), Equation(ren(q.expr), q.origin)) for x, v, q in r.definitions),
        joining,
    )


def _way(w: Way, f: Callable[[sp.Expr], sp.Expr]) -> Way:
    return Way(w.element, w.name, tuple(Equation(f(q.expr), q.origin) for q in w.equations), tuple(map(f, w.holds)))


def reduced(
    r: Relation, may_go: set[sp.Symbol] | None = None, unknown: set[sp.Symbol] | None = None, steady=None
) -> Relation:
    """Every variable that ``may_go`` (by default the circuit's own: not a named point's potential, not a
    parameter) an equation of degree one gives — its factor holding nothing ``unknown`` and ``steady`` (never
    0 as the circuit runs) — gone, defined. Never one on an end (the piece is seen by it), nor one inside a
    function anywhere. The equations go smallest first, a joining variable before an element's, again while
    any goes."""
    laws = dict(enumerate(r.laws))
    definitions, choices, taps, left, right = list(r.definitions), r.choices, r.taps, r.left, r.right
    boundary = {x for end in (*left, *right) for x in (*symbols_in(end.v), *symbols_in(end.i))}
    tangled = {x for q in laws.values() for f in q.expr.atoms(sp.Function) for x in symbols_in(f)}
    steady = steady or _steady

    def gone(x: sp.Symbol, value: sp.Expr, by: Equation) -> None:
        nonlocal choices, taps, left, right

        def put(e: sp.Expr) -> sp.Expr:
            return e.xreplace({x: value}) if e.has(x) else e

        definitions.append((x, value, by))
        for j, q in laws.items():
            if q.expr.has(x):
                laws[j] = Equation(normal(put(q.expr)), _reason(q, by, x))
        choices = tuple(tuple(_way(w, put) for w in c) for c in choices)
        taps = tuple((p, put(i)) for p, i in taps)
        left = tuple(End(put(e.v), put(e.i)) for e in left)
        right = tuple(End(put(e.v), put(e.i)) for e in right)
        tangled.update(y for f in value.atoms(sp.Function) for y in symbols_in(f))

    def going(e: sp.Expr) -> set[sp.Symbol]:
        here = symbols_in(e)
        return (
            here & may_go
            if may_go is not None
            else {x for x in here if isinstance(x, sp.Dummy) and x not in NAMED and x not in PARAMETERS}
        )

    def holding(e: sp.Expr) -> set[sp.Symbol]:
        return going(e) | (symbols_in(e) & unknown if unknown is not None else set()) | (symbols_in(e) & NAMED)

    progress = True
    while progress:
        progress = False
        for k in sorted(laws, key=lambda k: len(holding(laws[k].expr))):
            q = laws.get(k)
            if q is None:
                continue
            held = holding(q.expr)
            for x in sorted(going(q.expr) - tangled - boundary, key=lambda x: (x not in r.joining, str(x))):
                value = _alone(q.expr, x, held, steady)
                if value is not None:
                    del laws[k]
                    gone(x, value, q)
                    progress = True
                    break
    kept = tuple(q for q in laws.values() if q.expr != 0)
    return Relation(left, right, kept, choices, taps, tuple(definitions), r.joining)


def _alone(e: sp.Expr, x: sp.Symbol, held: set[sp.Symbol], steady) -> sp.Expr | None:
    """``x`` from ``e`` = 0, when ``e`` is of degree one in it and its factor holds no variable, is steady and
    is not zero."""
    a = sp.diff(e, x)
    if a.has(x) or symbols_in(a) & held or not steady(a) or sp.expand(a) == 0:
        return None
    return normal(-(e - a * x) / a)


def _steady(a: sp.Expr) -> bool:
    """A factor that is never 0 as the circuit runs: no function in it (a state, a switch: 0 one moment), nor
    a time word."""
    return not a.atoms(sp.Function) and not a.has(TIME, D, Pre)


def _reason(q: Equation, by: Equation, x: sp.Symbol) -> Origin:
    """A wire's equation says nothing of itself: with what a law said put in, it is that law's."""
    return by.origin if q.origin.what == "wire" and q.expr.has(x) and by.origin.what != "wire" else q.origin


def said(r: Relation) -> str:
    """A relation of one end each side as ``U = …`` (or ``I = …``), its voltage and current at its ends."""
    if len(r.left) == len(r.right) == 1 and not r.choices:
        U, I = sp.symbols("U I")
        (a,), (b,) = r.left, r.right
        eqs = [q.expr for q in r.laws] + [U - (a.v - b.v), I - a.i]
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
    return "; ".join(f"{q.expr} = 0" for q in r.laws)
