"""Every circuit is a component: ``E >> R`` is a new one, its ends the ends left free, its laws the laws of
both with what is between them eliminated. An element is a component of one piece; nothing else differs.

A component is a relation of its ends — at each, a potential and a current (in at a left end, out at a right
one) — built as the circuit is:

- an element: its laws, as its kind says them (time words and all: no frame yet, no data);
- a spider (a point): one potential at all its ends, what comes in goes out (Kirchhoff);
- ``swap``: two ends crossing;
- ``f @ g``: both, side by side;
- ``f >> g``: ``f``'s right ends are ``g``'s left ends — and what is then inside goes (∃, as composing
  relations hides what two pieces share), its definition kept: the component's own inner quantity, still
  there to be asked (``I(R)``). ``R_1 >> R_2`` so comes to one law of its ends, ``U = (R_1 + R_2)·I``.

A ``Node`` or ``Net`` is a named end: its potential one variable wherever it is, the currents into it met at
the top. A variable goes by an equation of degree one in it whose factor holds no variable of the circuit;
one under a time word, or inside an ``exp``, stays — for when the frame and the data are known
(``framed``). Nothing here knows any element.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from functools import cache

import sympy as sp

from ..circuit.kind import Terminals
from ..circuit.time import TIME
from ..circuit.tree import GND, Circuit, Element, Net, Node, Seq, Spider, Swap, Tensor
from ..problem.problem import Problem
from .analysis import Step, interpret, is_before
from .expressions import expr, subs, symbols_in
from .laws import inner_names, ways
from .relation import Equation, Origin, Way
from .symbols import Symbols, symbols
from .system import System, conditions_of, parameter_values, scaled_sources

Definition = tuple[sp.Symbol, sp.Expr, Equation]

GLUE: set[sp.Symbol] = set()
"""What only joins — a spider's, a crossing's, a named point's own currents and potential: gone first."""

NAMED: set[sp.Symbol] = set()
"""A named point's potential: one variable wherever the point is, never gone inside a component."""

PARAMETERS: set[sp.Symbol] = set()
"""An unnamed element's parameters: data, not the circuit's variables."""


@dataclass(frozen=True)
class End:
    v: sp.Expr
    i: sp.Expr


@dataclass(frozen=True)
class Component:
    """``left`` and ``right``: its ends; ``laws``: what holds between them (and what could not go);
    ``choices``: the ways of its elements of several; ``taps``: the current into each named point from it;
    ``definitions``: each inner quantity eliminated, in order — ``x = value``, by ``eq``."""

    left: tuple[End, ...]
    right: tuple[End, ...]
    laws: tuple[Equation, ...] = ()
    choices: tuple[tuple[Way, ...], ...] = ()
    taps: tuple[tuple[Node | Net, sp.Expr], ...] = ()
    definitions: tuple[Definition, ...] = ()

    def __str__(self) -> str:
        """A piece of one end each side as a book writes it: its voltage ``U`` (the first end against the second)
        by its current ``I`` (in at the first) — ``U = I·(R_1 + R_2)``; else its laws."""
        if len(self.left) == len(self.right) == 1 and not self.choices:
            U, I = sp.symbols("U I")
            (a,), (b,) = self.left, self.right
            eqs = [eq.expr for eq in self.laws] + [U - (a.v - b.v), I - a.i]
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
                left = {sp.factor(sp.expand(subs(e, by[0]))) for e in eqs} - {0}
                if not {x for e in left for x in symbols_in(e) if isinstance(x, sp.Dummy)}:
                    return "; ".join(f"{e} = 0" for e in left)
        return "; ".join(f"{eq.expr} = 0" for eq in self.laws)


@dataclass(frozen=True)
class Own:
    """An element's own variables: each terminal's potential, the current into it there, its parameters and
    inner quantities."""

    V: Mapping[str, sp.Expr]
    I: Mapping[str, sp.Expr]
    params: Mapping[str, sp.Symbol]
    inner: Mapping[str, sp.Symbol]


@cache
def own(e: Element) -> Own:
    ts = e.kind.terminals
    V = {t: sp.Integer(0) if e.kind.ground and t == ts[-1] else sp.Dummy(f"v_{t}") for t in ts}
    mine = {t: sp.Dummy(f"i_{t}") for t in ts[:-1]}
    I = {**mine, ts[-1]: -sp.Add(*mine.values())}
    params = {
        w: sp.Symbol(f"{w}_{e.name}" if w else e.name) if e.name else sp.Dummy(w or "p") for w in e.kind.parameters
    }
    PARAMETERS.update(x for x in params.values() if isinstance(x, sp.Dummy))
    inner = {name: sp.Dummy(name) for name in inner_names(e.kind)}
    return Own(V, I, params, inner)


@cache
def _named(p: Node) -> sp.Symbol:
    x = sp.Dummy(f"V_{p.label or ''}")
    NAMED.add(x)
    return x


def potential(p: Node | Net) -> sp.Expr:
    """A named point's potential: ground's 0."""
    if p == GND:
        return sp.Integer(0)
    if isinstance(p, Net):
        x = sp.Symbol(f"V_{p.name}")
        NAMED.add(x)
        return x
    return _named(p)


def _glue(name: str) -> sp.Symbol:
    x = sp.Dummy(name)
    GLUE.add(x)
    return x


def component(c: Circuit) -> Component:
    """``c`` as a component, its joining variables fresh: the same spider, ``Net`` or piece without elements
    may stand in several places, each its own."""
    match c:
        case Element():
            return _element(c)
        case Spider(dom, cod):
            v = _glue("v")
            ins, outs = [_glue("i") for _ in range(dom)], [_glue("i") for _ in range(cod)]
            kcl = (Equation(sp.Add(*ins) - sp.Add(*outs), Origin("kcl", None)),) if ins or outs else ()
            return Component(tuple(End(v, i) for i in ins), tuple(End(v, i) for i in outs), kcl)
        case Swap():
            a, b = End(_glue("v"), _glue("i")), End(_glue("v"), _glue("i"))
            return Component((a, b), (b, a))
        case Node() | Net():
            v, into, out = potential(c), _glue("i"), _glue("i")
            return Component((End(v, into),), (End(v, out),), taps=((c, into - out),))
        case Tensor(a, b):
            return _beside(component(a), component(b))
        case Seq(a, b):
            return reduced(_glued(component(a), component(b)))
    raise TypeError(c)


def _element(e: Element) -> Component:
    o = own(e)
    ts = e.kind.terminals
    cases = ways(e.kind.laws(Terminals(o.V, o.I, lambda name: o.inner[name]), o.params))

    def laws(case) -> tuple[Equation, ...]:
        return tuple(Equation(law, Origin("law", e, i, case.name)) for i, law in enumerate(case.laws))

    if len(cases) == 1:
        equations, choices = laws(cases[0]), ()
    else:
        equations, choices = (), (tuple(Way(e, c.name, laws(c), c.holds) for c in cases),)
    if len(ts) == 2:
        return Component((End(o.V[ts[0]], o.I[ts[0]]),), (End(o.V[ts[1]], -o.I[ts[1]]),), equations, choices)
    ends = ts[:-1] if e.kind.ground else ts
    return Component((), tuple(End(o.V[t], -o.I[t]) for t in ends), equations, choices)


def _beside(a: Component, b: Component) -> Component:
    return Component(
        a.left + b.left,
        a.right + b.right,
        a.laws + b.laws,
        a.choices + b.choices,
        a.taps + b.taps,
        a.definitions + b.definitions,
    )


def _glued(a: Component, b: Component) -> Component:
    """``a``'s right ends onto ``b``'s left ends: a potential and a current each."""
    wires = []
    for x, y in zip(a.right, b.left, strict=True):
        for one, other in ((x.v, y.v), (x.i, y.i)):
            if sp.expand(one - other) != 0:
                wires.append(Equation(one - other, Origin("wire", None)))
    both = _beside(a, b)
    return replace(both, left=a.left, right=b.right, laws=(*both.laws, *wires))


def _circuits(e: sp.Expr) -> set[sp.Symbol]:
    """The circuit's own variables in ``e`` (a named point's potential aside)."""
    return {x for x in symbols_in(e) if isinstance(x, sp.Dummy) and x not in NAMED and x not in PARAMETERS}


def reduced(c: Component, may_go: set[sp.Symbol] | None = None, unknown: set[sp.Symbol] | None = None) -> Component:
    """Every variable that ``may_go`` an equation of degree one gives, its factor holding nothing ``unknown``:
    gone, defined. By default the circuit's own variables, a named point's potential aside."""
    laws, definitions, choices, taps, left, right = (
        list(c.laws),
        list(c.definitions),
        c.choices,
        c.taps,
        c.left,
        c.right,
    )
    boundary = {x for end in (*left, *right) for x in (*symbols_in(expr(end.v)), *symbols_in(expr(end.i)))}
    while (found := _next(laws, may_go, unknown, boundary)) is not None:
        x, eq, value = found
        definitions.append((x, value, eq))
        at = {x: value}

        def put(e: sp.Expr, at=at) -> sp.Expr:
            return subs(e, at) if e.has(*at) else e

        laws = [Equation(_normal(put(q.expr)), _reason(q, eq, x)) for q in laws if q is not eq]
        choices = tuple(
            tuple(
                Way(
                    w.element,
                    w.name,
                    tuple(Equation(put(q.expr), q.origin) for q in w.equations),
                    tuple(map(put, w.holds)),
                )
                for w in choice
            )
            for choice in choices
        )
        taps = tuple((q, put(i)) for q, i in taps)
        left = tuple(End(put(e.v), put(e.i)) for e in left)
        right = tuple(End(put(e.v), put(e.i)) for e in right)
    return Component(left, right, tuple(q for q in laws if q.expr != 0), choices, taps, tuple(definitions))


def _next(
    laws: list[Equation],
    may_go: set[sp.Symbol] | None,
    unknown: set[sp.Symbol] | None,
    boundary: set[sp.Symbol] | frozenset = frozenset(),
):
    """What to eliminate next: in the equation with fewest variables, a joining one first; never one on the
    ``boundary`` (an end: the piece is seen by it), nor one inside a function anywhere (an ``exp``'s, a time
    word's) — what is tangled so is left whole, for Newton."""
    tangled = {x for eq in laws for f in eq.expr.atoms(sp.Function) for x in symbols_in(f)}
    ranked = []
    for eq in laws:
        here = symbols_in(eq.expr)
        circuit = _circuits(eq.expr) if may_go is None else here & may_go
        holding = circuit | (here & unknown if unknown is not None else set()) | (here & NAMED)
        free = circuit - tangled - boundary
        if free:
            ranked.append((len(holding), eq, holding, free))
    for _, eq, holding, free in sorted(ranked, key=lambda r: r[0]):
        for x in sorted(free, key=lambda x: (x not in GLUE, str(x))):
            value = _alone(eq.expr, x, holding)
            if value is not None:
                return x, eq, value
    return None


def _alone(e: sp.Expr, x: sp.Symbol, variables: set[sp.Symbol]) -> sp.Expr | None:
    """``x`` from ``e`` = 0, when ``e`` is of degree one in it and its factor holds no variable and is not
    zero."""
    a = sp.diff(e, x)
    if a.has(x) or symbols_in(a) & variables or sp.expand(a) == 0:
        return None
    return sp.cancel(-(e - a * x) / a)


def _reason(q: Equation, by: Equation, x: sp.Symbol) -> Origin:
    """A wire's equation says nothing of itself: with what a law said put in, it is that law's."""
    return by.origin if q.origin.what == "wire" and q.expr.has(x) and by.origin.what != "wire" else q.origin


def _normal(e: sp.Expr) -> sp.Expr:
    """An equation (= 0) over one common denominator, cancelled: 0 when it holds whatever the values. The
    denominator stays — cleared, its zeros would be roots that are none. One with a function in it (an
    ``exp``) is left as its law says it: brought over one denominator, an exponential multiplies through and
    grows past any float."""
    return e if e.atoms(sp.Function) else sp.cancel(e)


def resolve(e: sp.Expr, definitions) -> sp.Expr:
    """``e`` in what is left: each eliminated variable by its definition, in order."""
    for x, value, _ in definitions:
        if e.has(x):
            e = subs(e, {x: value})
    return sp.expand(e)


# The top: the whole circuit's component, named as a book names it, read in a frame with the data in.


@dataclass(frozen=True)
class Framed:
    """What is left to solve (``system``), and how every variable comes back from it (``complete``)."""

    system: System
    definitions: tuple[Definition, ...]

    def complete(self, values: Mapping[sp.Symbol, sp.Expr]) -> dict[sp.Symbol, sp.Expr]:
        """Every variable from what was found: each eliminated one, the last first."""
        out = dict(values)
        for x, value, _ in reversed(self.definitions):
            out[x] = _tidy(subs(value, out))
        return out


def names(s: Symbols) -> tuple[dict[sp.Symbol, sp.Expr], set[sp.Symbol]]:
    """Each element's own variables and each named point's potential as a book names them (``I_R_1``,
    ``R_1``, ``V_A``, ``V_3``; 0 at a reference), and which of them are a terminal's potential — several
    of those are one point's."""
    out: dict[sp.Symbol, sp.Expr] = {}
    at_points: set[sp.Symbol] = set()
    for k, (e, _) in enumerate(s.net.parts):
        o, t = own(e), s.terminals(k)
        for name in e.kind.terminals:
            if isinstance(v := o.V[name], sp.Symbol):
                out[v] = t.V[name]
                at_points.add(v)
        out |= {x: t.I[name] for name, x in o.I.items() if isinstance(x, sp.Symbol)}
        out |= {x: s.param(e, w) for w, x in o.params.items()}
        out |= {x: sp.Symbol(f"{name}_{s.labels[k]}") for name, x in o.inner.items()}
    for n, p in s.net.named:
        if isinstance(v := potential(p), sp.Symbol):
            out[v] = s.potentials[n]
            at_points.add(v)
    return out, at_points


def framed(
    problem: Problem, analysis: Step, letters: Mapping[sp.Symbol, sp.Expr] | None = None, sources: sp.Expr | int = 1
) -> Framed:
    """The whole circuit's component named, read in ``analysis`` with the data and ``letters`` in (every
    independent source scaled by ``sources``), what joins it to itself and the data on quantities added,
    reduced again. A terminal's potential is its point's: what defined it becomes an equation of the point."""
    s = symbols(problem.circuit)
    whole = component(problem.circuit)
    to, at_points = names(s)
    values = {**parameter_values(problem, s), **(letters or {})}
    if sources != 1:
        values = scaled_sources(values, s, sources)

    def read(e: sp.Expr) -> sp.Expr:
        return analysis.timed(subs(interpret(e.xreplace(to), analysis), values))

    top = [
        Equation(sp.Add(*(i for q, i in whole.taps if q == p)), Origin("kcl", n))
        for n, p in s.net.named
        if s.potentials[n] != 0
    ]
    top += [Equation(end.i, Origin("kcl", None)) for end in (*whole.left, *whole.right)]
    laws = [Equation(read(eq.expr), eq.origin) for eq in (*whole.laws, *top)]
    definitions, of_points = [], []
    for x, v, eq in whole.definitions:
        if x in at_points:
            of_points.append(Equation(read(x - v), eq.origin))
        else:
            definitions.append((to.get(x, x), read(v), Equation(read(eq.expr), eq.origin)))
    laws += [
        Equation(resolve(eq.expr, definitions), eq.origin) for eq in (*of_points, *conditions_of(problem, s, s.of))
    ]
    choices = tuple(
        tuple(
            Way(
                w.element,
                w.name,
                tuple(Equation(read(q.expr), q.origin) for q in w.equations),
                tuple(map(read, w.holds)),
            )
            for w in choice
        )
        for choice in whole.choices
    )
    known = {x for v in values.values() for x in symbols_in(expr(v))} | analysis.letters() | {TIME}
    appearing = {x for eq in laws for x in symbols_in(eq.expr)}
    appearing |= {x for c in choices for w in c for eq in w.equations for x in symbols_in(eq.expr)}
    variables = {x for x in appearing - known if not is_before(x)}
    params = {p for e, _ in s.net.parts for p in s.params(e).values()} - set(values)
    left = reduced(Component((), (), tuple(laws), choices, (), tuple(definitions)), variables - params, variables)
    eqs = _once(Equation(_normal(eq.expr), eq.origin) for eq in left.laws)
    unknowns = {x for eq in eqs for x in symbols_in(eq.expr)} & variables
    unknowns |= {x for c in left.choices for w in c for eq in w.equations for x in symbols_in(eq.expr)} & variables
    unknowns |= params
    positive = {s.param(e, w) for e, _ in s.net.parts for w in e.kind.positive} & unknowns
    system = System(
        eqs, tuple(sorted(unknowns, key=str)), s, left.choices, frozenset(positive), frozenset(params & unknowns)
    )
    return Framed(system, left.definitions)


def _once(eqs) -> tuple[Equation, ...]:
    """Each equation once (one point's several terminals say its potential each), none that always holds."""
    seen: set[sp.Expr] = set()
    out = []
    for eq in eqs:
        if eq.expr == 0 or eq.expr in seen or -eq.expr in seen:
            continue
        seen.add(eq.expr)
        out.append(eq)
    return tuple(out)


def _tidy(e: sp.Expr) -> sp.Expr:
    """A value as short as it cheaply gets: letters cancelled; numbers as they are (simplifying 10^0.7 and
    its kin can take sympy forever)."""
    return sp.cancel(e) if e.free_symbols else e
