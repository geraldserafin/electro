"""A closed circuit's frame formula, a pipeline: the circuit closed (``close``: renamed as a book names it,
Kirchhoff at its points), read in a frame with its values in (``formula``: ``Laws.map`` of the frame's
reading), and what can go gone again — what is left to solve and, in the log, how every quantity comes
back. What goes in (the values, what was a frame before, the time, letters) is a substitution the caller
makes; nothing here knows any kind of element.

Its variables are named as a book names them: ``I_R_1``, ``R_1``, ``V_A``. Where nothing fixes how high its
potentials stand (no ground in a piece), one of them is chosen 0: the laws only ever speak of differences
there — they hold whatever is added to all — so the choice is free.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import cast

import sympy as sp

from ..circuit.algebra import Equation, Known, Laws, Origin, expr, linear, normal, symbols_in
from ..circuit.element import NAMED, POTENTIALS, Element
from ..circuit.names import Names, names
from ..circuit.quantities import Potential, Quantity, Scaled
from ..circuit.time import TIME, D, Pre
from ..values import UNKNOWN, parse
from .reading import DT, Step, interpret, is_before


class NotClosed(ValueError):
    """Only a closed circuit has values: ``left`` and ``right`` ends are still free (not on a named point)."""

    def __init__(self, left: int, right: int) -> None:
        super().__init__(left, right)
        self.left, self.right = left, right


class NoSuchParameter(ValueError):
    """A value given for a name no element has."""


@dataclass(frozen=True)
class Closed:
    """A closed circuit as a book writes it: its laws in its names (``names``), Kirchhoff at its points, still
    in the words of time; ``points``: its named points' potentials."""

    circuit: Element
    names: Names
    laws: Laws
    points: frozenset[sp.Symbol]

    @property
    def remembered(self) -> tuple[frozenset[sp.Expr], frozenset[sp.Expr]]:
        """What its laws keep under ``D``, and under ``Pre``."""
        said = self.laws.expressions()
        return tuple(frozenset(expr(a.args[0]) for e in said for a in e.atoms(w)) for w in (D, Pre))  # type: ignore[return-value]


def close(circuit: Element, leak: float = 0.0) -> Closed:
    """``circuit``, whole: renamed as a book names it, what comes into each named point 0 (``leak``: a whisper
    of a conductance from each to ground), nothing coming in at its ends."""
    if circuit.free != (0, 0):
        raise NotClosed(*circuit.free)
    n = names(circuit)
    rel = circuit.rel.map(n.rename)
    points = {p: n.of(Potential(p)) for p in dict.fromkeys(q for q, _ in rel.taps)}
    kcl = [
        Equation(sp.Add(*(i for q, i in rel.taps if q == p)) + leak * v, Origin("kcl", p))
        for p, v in points.items()
        if v != 0
    ]
    kcl += [Equation(end.i, Origin("kcl", None)) for end in (*rel.left, *rel.right)]
    return Closed(
        circuit, n, rel.laws & Laws(tuple(kcl)), frozenset(v for v in points.values() if isinstance(v, sp.Symbol))
    )


@dataclass(frozen=True)
class Formula:
    """What is left to solve (``laws``: its equations and ways; in its log, what went on the way) over its
    ``unknowns`` — those never negative ``positive``, its parameters not given ``params``."""

    laws: Laws
    unknowns: tuple[sp.Symbol, ...]
    names: Names
    given: Known = field(default_factory=dict)
    positive: frozenset[sp.Symbol] = frozenset()
    params: frozenset[sp.Symbol] = frozenset()


def formula(
    c: Closed, frame: Step, given: Known, data: tuple[Equation, ...] = (), keep: frozenset = frozenset()
) -> Formula:
    """``c`` read in ``frame`` (a functor: ``D`` and ``Pre`` become one frame's equations), ``given`` in, the
    ``data`` (equations on its quantities) with it, a potential chosen 0 where nothing fixes them, and every
    variable but ``keep`` that can go, gone."""
    read = frame.reading(given)
    laws = c.laws.map(read)
    laws &= Laws(tuple(Equation(laws.resolve(read(q.expr)), q.origin) for q in data))
    laws &= Laws(_references(laws, {c.names.to.get(v, v) for v in POTENTIALS | NAMED}))
    known = {x for v in given.values() for x in symbols_in(v)} | frame.letters() | {TIME}
    variables = {x for q in _said(laws) for x in symbols_in(q.expr)} - known
    variables = {x for x in variables if not is_before(x)}
    params = {p.xreplace(c.names.to) for e in c.circuit.members for p in e.P.values()} - set(given)
    left = laws.eliminate(variables - params, linear(variables, _steady), keep=keep)
    left = Laws(_once(Equation(normal(q.expr), q.origin) for q in left.equations), left.choices, left.log)
    unknowns = ({x for q in _said(left) for x in symbols_in(q.expr)} & variables) | params
    positive = {e.P[w].xreplace(c.names.to) for e in c.circuit.members for w in e.positive} & unknowns
    return Formula(
        left, tuple(sorted(unknowns, key=str)), c.names, given, frozenset(positive), frozenset(params & unknowns)
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


def scaled(given: Known, circuit: Element, n: Names, by: sp.Expr) -> Known:
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
