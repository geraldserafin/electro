"""A closed circuit's frame formula: its relation renamed as a book names it, read in a frame (a functor:
``D`` and ``Pre`` become one frame's equations), its values in, Kirchhoff at its named points, and what can
go hidden again — what is left to solve and, in the log, how every quantity comes back. Nothing here knows
any kind of element.

Its variables are named as a book names them: ``I_R_1``, ``R_1``, ``V_A``. Where nothing fixes how high its
potentials stand (no ground in a piece), one of them is chosen 0: the laws only ever speak of differences
there — they hold whatever is added to all — so the choice is free.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import cast

import sympy as sp

from ..circuit.algebra import Equation, Known, Laws, Origin, expr, linear, normal, symbols_in
from ..circuit.element import NAMED, POTENTIALS, Element
from ..circuit.points import Node
from ..circuit.quantities import Across, Current, Parameter, Potential, Power, Quantity, Scaled, Sum, Voltage
from ..circuit.time import TIME, D, Pre
from ..values import UNKNOWN, parse
from .reading import DT, Step, before, interpret, is_before


class NotClosed(ValueError):
    """Only a closed circuit has values: ``left`` and ``right`` ends are still free (not on a named point)."""

    def __init__(self, left: int, right: int) -> None:
        super().__init__(left, right)
        self.left, self.right = left, right


class NoSuchParameter(ValueError):
    """A value given for a name no element has."""


@dataclass(frozen=True)
class Names:
    """A closed circuit's elements by their labels (``R_1``) and its variables by the names a book gives
    them."""

    labels: Mapping[Element, str]
    to: Mapping[sp.Symbol, sp.Expr]
    points: Mapping[Node, sp.Expr]

    def of(self, q: Quantity | Scaled) -> sp.Expr:
        """A quantity in the named variables."""
        match q:
            case Current(e, at):
                return e.I[at or e.terminals[0]].xreplace(self.to)
            case Voltage(e):
                a, b = e.terminals[:2]
                return (e.V[a] - e.V[b]).xreplace(self.to)
            case Parameter(e, which):
                return e.P[which].xreplace(self.to)
            case Potential(p):
                return self.points.get(p, p.potential)
            case Across(a, b):
                return self.of(Potential(a)) - self.of(Potential(b))
            case Power(e):
                return self.of(Voltage(e)) * self.of(Current(e))
            case Scaled(k, x):
                return k * self.of(x)
            case Sum(terms):
                return sp.Add(*(self.of(t) for t in terms))
        raise TypeError(q)


def names(circuit: Element) -> Names:
    labels = _labels(circuit.members)
    to: dict[sp.Symbol, sp.Expr] = {}
    for e in circuit.members:
        label = labels[e]
        for t, v in e.V.items():
            if isinstance(v, sp.Symbol):
                to[v] = sp.Symbol(f"V_{label}_{t}")
        two = len(e.terminals) == 2
        to |= {
            x: sp.Symbol(f"I_{label}" if two else f"I_{label}_{t}") for t, x in e.I.items() if isinstance(x, sp.Symbol)
        }
        base = e.name or label
        to |= {x: sp.Symbol(f"{w}_{base}" if w else base) for w, x in e.P.items() if isinstance(x, sp.Dummy)}
        to |= {x: sp.Symbol(f"{name}_{label}") for name, x in e.inner.items()}
    points = {}
    every = _points(circuit)
    alike = Counter(p.label for p in every)
    for k, p in enumerate(every, 1):
        if isinstance(p.potential, sp.Dummy):
            points[p] = sp.Symbol(f"V_{p.label}" if p.label and alike[p.label] == 1 else f"V_n{k}")
            to[p.potential] = points[p]
    return Names(labels, to, points)


@dataclass(frozen=True)
class Formula:
    """What is left to solve (``laws``: its equations and ways; in its log, what went on the way) over its
    ``unknowns`` — those never negative ``positive``, its parameters not given ``params``; ``remembered``:
    what the laws keep under ``D`` and under ``Pre``; ``time``: the frame's end."""

    laws: Laws
    unknowns: tuple[sp.Symbol, ...]
    names: Names
    values: Known = field(default_factory=dict)
    positive: frozenset[sp.Symbol] = frozenset()
    params: frozenset[sp.Symbol] = frozenset()
    remembered: tuple[frozenset[sp.Expr], frozenset[sp.Expr]] = (frozenset(), frozenset())
    time: sp.Expr = sp.oo


def formula(
    circuit: Element,
    values: Mapping,
    frame: Step,
    after=None,
    *,
    kept: bool = False,
    letters: Mapping[sp.Symbol, sp.Expr] | None = None,
    sources: sp.Expr | int = 1,
    leak: float = 0.0,
) -> Formula:
    """The closed ``circuit`` read in ``frame`` after the frame ``after`` (a solution; by default from rest),
    ``values`` in (its elements' values, and data on quantities: ``{R: "1k", I(R): 2}``) and ``letters``
    (every independent source scaled by ``sources``). ``kept``: what was a frame before and the time stay
    letters — the frame as a function of them, its named points' potentials kept among what is found (each
    gone, the next is worked out from it: a ladder of them is a polynomial in 1/dt of its length, numbers
    no float holds). ``leak``: a whisper of a conductance from each named point to ground."""
    if circuit.free != (0, 0):
        raise NotClosed(*circuit.free)
    n = names(circuit)
    rel = circuit.rel.map(lambda e: e.xreplace(n.to))
    given = {**parameter_values(circuit, values, n), **(letters or {})}
    if sources != 1:
        given = _scaled(given, circuit, n, sources)
    said = rel.laws.expressions()
    under_d = frozenset(expr(a.args[0]) for e in said for a in e.atoms(D))
    under_pre = frozenset(expr(a.args[0]) for e in said for a in e.atoms(Pre))
    time = sp.oo
    if not kept:
        given |= {before(x): after.evaluated(x) if after is not None else sp.Integer(0) for x in under_d | under_pre}
        if frame.dt not in (0, sp.oo):
            time = (after.time if after is not None else sp.Integer(0)) + frame.dt
            given[TIME] = time

    def read(e: sp.Expr) -> sp.Expr:
        return frame.timed((interpret(e, frame) if e.has(D, Pre) else e).xreplace(given))

    points = {p: n.of(Potential(p)) for p in _points(circuit)}
    kcl = [
        Equation(sp.Add(*(i for q, i in rel.taps if q == p)) + leak * v, Origin("kcl", p))
        for p, v in points.items()
        if v != 0
    ]
    kcl += [Equation(end.i, Origin("kcl", None)) for end in (*rel.left, *rel.right)]
    laws = (rel.laws & Laws(tuple(kcl))).map(read)
    laws &= Laws(tuple(Equation(laws.resolve(read(q.expr)), q.origin) for q in conditions(values, n)))
    laws &= Laws(_references(laws, {n.to.get(v, v) for v in POTENTIALS | NAMED}))
    known = {x for v in given.values() for x in symbols_in(v)} | frame.letters() | {TIME}
    appearing = {x for q in _said(laws) for x in symbols_in(q.expr)}
    variables = {x for x in appearing - known if not is_before(x)}
    params = {p.xreplace(n.to) for e in circuit.members for p in e.P.values()} - set(given)
    staying = {v for v in points.values() if isinstance(v, sp.Symbol)} if kept else set()
    left = laws.eliminate(variables - params - staying, linear(variables, _steady))
    left = Laws(_once(Equation(normal(q.expr), q.origin) for q in left.equations), left.choices, left.log)
    unknowns = ({x for q in _said(left) for x in symbols_in(q.expr)} & variables) | params
    positive = {e.P[w].xreplace(n.to) for e in circuit.members for w in e.positive} & unknowns
    return Formula(
        left,
        tuple(sorted(unknowns, key=str)),
        n,
        given,
        frozenset(positive),
        frozenset(params & unknowns),
        (under_d, under_pre),
        time,
    )


def _said(laws: Laws) -> list[Equation]:
    """Its equations and its ways'."""
    return [*laws.equations, *(q for c in laws.choices for w in c for q in w.equations)]


def parameter_values(circuit: Element, values: Mapping, n: Names) -> Known:
    """Each parameter's value: as given, else its kind's default. An element's value is its main parameter;
    several by name (``{D: {"I_S": …}}``); a real part's (``part("1N4148")``); a name shared by elements."""
    from ..parts import Part

    out: Known = {}
    for e in circuit.members:
        out |= {e.P[w].xreplace(n.to): expr(parse(d)) for w, d in e.defaults.items()}
    for key, value in values.items():
        value = _read(value)
        if value is UNKNOWN:
            continue
        match key:
            case Element() if isinstance(value, Part):
                out |= {key.P[w].xreplace(n.to): expr(parse(x)) for w, x in value.parameters(key.kind).items()}
            case Element() if isinstance(value, Mapping):
                out |= {key.P[w].xreplace(n.to): expr(parse(x)) for w, x in value.items() if parse(x) is not UNKNOWN}
            case Element():
                out[key.P[""].xreplace(n.to)] = cast(sp.Expr, value)
            case str():
                if not any(x.name == key for e in circuit.members for x in e.P.values() if isinstance(x, sp.Symbol)):
                    raise NoSuchParameter(key)
                out[sp.Symbol(key)] = cast(sp.Expr, value)
    return out


def conditions(values: Mapping, n: Names) -> list[Equation]:
    """The data on quantities (``I(R): 2``, ``U(R_1): 2 * U(R_2)``), each an equation."""
    out = []
    for key, value in values.items():
        if not isinstance(key, Quantity | Scaled):
            continue
        value = _read(value)
        if value is UNKNOWN:
            continue
        rhs = n.of(value) if isinstance(value, Quantity | Scaled) else cast(sp.Expr, value)
        out.append(Equation(n.of(key) - rhs, Origin("given", key)))
    return out


def _read(value: object) -> object:
    from ..parts import Part

    if isinstance(value, Mapping | Quantity | Scaled | Part):
        return value
    return parse(value)


def is_source(e: Element) -> bool:
    """An independent source: a law keeps a term with none of its own quantities in it (``U + E``, ``I − J``),
    read in DC (a capacitor's ``I − C·dU/dt`` keeps none)."""
    from .reading import DC

    own = [x for x in (*e.V.values(), *e.I.values(), *e.inner.values()) if isinstance(x, sp.Symbol)]
    zero = dict.fromkeys(own, sp.Integer(0))
    return not e.rel.laws.choices and any(
        sp.simplify(interpret(q.expr, DC()).xreplace(zero)) != 0 for q in e.rel.laws.equations
    )


def _scaled(given: dict, circuit: Element, n: Names, by) -> dict:
    """Every independent source's parameters scaled by ``by`` (Newton's way up from nothing)."""
    of_sources = {p.xreplace(n.to) for e in circuit.members if is_source(e) for p in e.P.values()}
    return {p: by * v if p in of_sources else v for p, v in given.items()}


def _references(laws: Laws, potentials: set[sp.Symbol]) -> tuple[Equation, ...]:
    """Where nothing fixes how high a piece's potentials stand — its laws (each way's too, and what each
    needs) hold whatever is added to all of them — one of them chosen 0."""
    said = [q.expr for q in _said(laws)] + [h for c in laws.choices for w in c for h in w.holds]
    groups: dict[sp.Symbol, sp.Symbol] = {}

    def find(x: sp.Symbol) -> sp.Symbol:
        while groups.setdefault(x, x) != x:
            x = groups[x]
        return x

    for e in said:
        here = sorted(symbols_in(e) & potentials, key=str)
        for a, b in zip(here, here[1:]):
            groups[find(a)] = find(b)
    pieces: dict[sp.Symbol, list[sp.Symbol]] = {}
    for x in groups:
        pieces.setdefault(find(x), []).append(x)
    out = []
    lifted = sp.Dummy("c")
    for members in pieces.values():
        members.sort(key=str)
        shift = {x: x + lifted for x in members}
        touched = [e for e in said if symbols_in(e) & set(members)]
        if touched and all(sp.expand(e.xreplace(shift) - e) == 0 for e in touched):
            out.append(Equation(members[0], Origin("reference", members[0])))
    return tuple(out)


def _steady(a: sp.Expr) -> bool:
    """A factor never 0 as the circuit runs: no function in it (a state, a switch: 0 one moment), nor the time,
    nor what was a frame before, nor the frame's length (C/dt is 0 in a frame infinitely long)."""
    return not a.atoms(sp.Function) and not any(y in (TIME, DT) or is_before(y) for y in symbols_in(a))


def _once(eqs) -> tuple[Equation, ...]:
    """Each equation once (one point's several terminals say its potential each), none that always holds."""
    seen: set[sp.Expr] = set()
    out = []
    for q in eqs:
        if q.expr == 0 or q.expr in seen or -q.expr in seen:
            continue
        seen.add(q.expr)
        out.append(q)
    return tuple(out)


def _labels(members: tuple[Element, ...]) -> dict[Element, str]:
    """An element's name when no other has it; the others numbered by their prefix in order (``R_1``,
    ``R_2``), past the names taken (``R1`` takes ``R_1`` too)."""
    named = [e.name for e in members]
    unique = {x for x in named if x and named.count(x) == 1}
    taken = {x.replace("_", "") for x in unique}
    counters: Counter[str] = Counter()
    out = {}
    for e in members:
        if e.name in unique:
            out[e] = e.name
            continue
        while True:
            counters[e.prefix] += 1
            label = f"{e.prefix}_{counters[e.prefix]}"
            if label.replace("_", "") not in taken:
                taken.add(label.replace("_", ""))
                out[e] = label
                break
    return out


def _points(circuit: Element) -> list[Node]:
    """Its named points, in the order they are first met."""
    out: list[Node] = []
    for p, _ in circuit.rel.taps:
        if p not in out:
            out.append(p)
    return out
