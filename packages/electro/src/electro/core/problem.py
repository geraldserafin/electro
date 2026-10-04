"""A circuit as one relation, a problem as one is set, and what answers it (DESIGN.md §13).

The core is relations (the category Rel, with nodes as its spiders): variables and equations, each
equation knowing where it comes from (an element's law, Kirchhoff at a point, a datum) — so a solution
can say its steps. A circuit's relation is the join of its elements' and its points' relations (a point:
one potential shared by all that meet there, and Kirchhoff's current law). Each analysis only reads the
time words in it: ``D`` (DC: 0, AC: jω, a step: the difference back) and ``Pre`` (DC, AC: itself; a step:
the value a step ago).
"""

from __future__ import annotations

import itertools
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from functools import cache
from types import MappingProxyType
from typing import cast

import sympy as sp

from electro.values import UNKNOWN, parse

from .numeric import Jacobian, Residual, compiled, homotopy, newton
from .syntax import (
    GND,
    TIME,
    Case,
    Cases,
    Circuit,
    D,
    Element,
    Kind,
    Net,
    Netlist,
    Node,
    Pre,
    Terminals,
    free,
    is_closed,
    netlist,
)

# sympy's own types are loose (``subs`` of a dict, ``replace`` gives ``Basic``): said once, here


def subs(x: sp.Expr, values: Mapping[sp.Symbol, sp.Expr] | Mapping[sp.Symbol, float]) -> sp.Expr:
    return cast(sp.Expr, x.subs(list(values.items())))


def _replace(x: sp.Expr, f: sp.FunctionClass, by: Callable[[sp.Expr], sp.Expr]) -> sp.Expr:
    return cast(sp.Expr, x.replace(f, by))


def _symbols_in(x: sp.Expr) -> set[sp.Symbol]:
    return {s for s in x.free_symbols if isinstance(s, sp.Symbol)}


# --------------------------------------------------------------------------------------- quantities


@dataclass(frozen=True)
class Current:
    of: Element
    at: str | None = None  # a terminal (an element of more than two); two: the current from a to b


@dataclass(frozen=True)
class Voltage:
    of: Element  # a two-terminal one's: the drop from a to b


@dataclass(frozen=True)
class Parameter:
    of: Element  # its value
    which: str = ""  # one of several (a diode's "I_S"); "": its main one


@dataclass(frozen=True)
class Potential:
    at: Node | Net


@dataclass(frozen=True)
class Across:
    a: Node | Net
    b: Node | Net  # V_a − V_b


Quantity = Current | Voltage | Parameter | Potential | Across


def I(e: Element, at: str | None = None) -> Current:  # noqa: E743 — as a book writes it
    return Current(e, at)


def U(a: Element | Node | Net, b: Node | Net | None = None) -> Voltage | Across:
    return Voltage(a) if isinstance(a, Element) else Across(a, b if b is not None else GND)


def V(p: Node | Net) -> Potential:
    return Potential(p)


# --------------------------------------------------------------------------------------- relations


@dataclass(frozen=True)
class Origin:
    """Where an equation comes from — what a step of a solution says as its reason."""

    what: str  # "law" (an element's), "kcl" (Kirchhoff at a point), "given" (a datum), "port", "holds"
    subject: object  # the element, the point (its number), the datum's key
    index: int = 0  # which of the element's laws
    case: str = ""  # the way the element is (a textbook diode "on"), when it is one of several


@dataclass(frozen=True)
class Equation:
    expr: sp.Expr  # = 0
    origin: Origin


@dataclass(frozen=True)
class Way:
    """One way an element may be, as part of a relation: its equations then, what must hold (≥ 0)."""

    element: Element
    name: str
    equations: tuple[Equation, ...]
    holds: tuple[sp.Expr, ...]


@dataclass(frozen=True)
class Relation:
    """Variables and equations: ``ends`` what is seen from outside, the rest inside. ``choices``: for each
    element of several ways, the ways — the relation is the union of one piece per choice (still a
    relation: a set of what may be, now in pieces)."""

    ends: tuple[sp.Symbol, ...]
    equations: tuple[Equation, ...]
    choices: tuple[tuple[Way, ...], ...] = ()


def join(*relations: Relation) -> Relation:
    """Together: every equation of each; a variable they share is one (that is how they are joined)."""
    ends = tuple(dict.fromkeys(x for r in relations for x in r.ends))
    return Relation(
        ends, tuple(eq for r in relations for eq in r.equations), tuple(c for r in relations for c in r.choices)
    )


def hide(r: Relation, ends: Sequence[sp.Symbol]) -> Relation:
    """Seen from outside only through ``ends`` (the rest is inside: eliminated when it is solved)."""
    return Relation(tuple(ends), r.equations, r.choices)


# --------------------------------------------------------------------------------------- problem


class NotClosed(ValueError):
    """Only a circuit with nothing left to connect is a problem (a piece: ``blackbox``)."""


class NoSuchParameter(ValueError):
    """A value given for a name no element has."""


class Undetermined(ValueError):
    """What is sought does not follow from what is given."""


Key = Element | str | Quantity


@dataclass(frozen=True)
class Problem:
    circuit: Circuit
    given: Mapping[Key, object] = field(default_factory=dict)
    find: Sequence[Quantity] = ()

    def __post_init__(self) -> None:
        # (read once, as it is built — values parsed, nothing to change it after; an element of several
        # parameters may be given them by name: {diode: {"I_S": "1e-14", "n": 1}})
        object.__setattr__(
            self,
            "given",
            MappingProxyType(
                {
                    k: MappingProxyType({w: parse(x) for w, x in v.items()}) if isinstance(v, Mapping) else parse(v)
                    for k, v in self.given.items()
                }
            ),
        )
        object.__setattr__(self, "find", tuple(self.find))
        if not is_closed(self.circuit):
            raise NotClosed()
        names = {e.name for e, _ in netlist(self.circuit).parts}
        for k in self.given:
            if isinstance(k, str) and k not in names:
                raise NoSuchParameter(k)

    @property
    def values(self) -> Mapping[Key, sp.Expr]:
        """What is given of single values, each (an unknown left out)."""
        return {k: cast(sp.Expr, v) for k, v in self.given.items() if v is not UNKNOWN and not isinstance(v, Mapping)}


# --------------------------------------------------------------------------------------- analyses


@dataclass(frozen=True)
class DC: ...


@dataclass(frozen=True)
class AC:
    omega: sp.Expr


@dataclass(frozen=True)
class Step:
    dt: sp.Expr


Analysis = DC | AC | Step


def before(x: sp.Expr) -> sp.Symbol:
    """``x`` a step ago (what a step in time remembers)."""
    return sp.Symbol(f"{x}⁻")


def interpret(law: sp.Expr, analysis: Analysis) -> sp.Expr:
    """A law in an analysis: its time words read as the analysis reads them."""
    match analysis:
        case DC():
            return _replace(_replace(law, D, lambda x: sp.Integer(0)), Pre, lambda x: x)
        case AC(omega):
            return _replace(_replace(law, D, lambda x: sp.I * omega * x), Pre, lambda x: x)
        case Step(dt):
            return _replace(_replace(law, D, lambda x: (x - before(x)) / dt), Pre, before)
    raise TypeError(analysis)


# --------------------------------------------------------------------------------------- what laws say of themselves


def ways(laws: Sequence[sp.Expr] | Cases) -> tuple[Case, ...]:
    """A kind's laws as its ways: one (plain laws), or its cases."""
    return laws.cases if isinstance(laws, Cases) else (Case("", tuple(sp.sympify(x) for x in laws)),)


def _own(kind: Kind) -> tuple[tuple[Case, ...], list[sp.Symbol]]:
    """A kind's ways over symbols of its own (a potential and a current per terminal), and those."""
    V = {t: sp.Symbol(f"v_{t}") for t in kind.terminals}
    I = {t: sp.Symbol(f"i_{t}") for t in kind.terminals}  # noqa: E741
    params = {w: sp.Symbol(f"p_{w}") for w in kind.parameters}
    return ways(kind.laws(Terminals(V, I, lambda n: sp.Symbol(f"x_{n}")), params)), [*V.values(), *I.values()]


def is_linear(e: Element, analysis: Analysis | None = None) -> bool:
    """Its laws of degree one in its potentials and currents (a resistor, a source, a capacitor read by
    any analysis, a controlled source — not a diode, and not one of several ways: piecewise)."""
    cases, xs = _own(e.kind)
    if len(cases) != 1:
        return False
    (only,) = cases
    laws = [sp.sympify(x) for x in only.laws]
    try:
        return all(sp.Poly(sp.expand(interpret(law, analysis or DC())), *xs).total_degree() <= 1 for law in laws)
    except sp.PolynomialError:  # (exp(U), a diode's: not a polynomial at all)
        return False


def is_source(e: Element) -> bool:
    """An independent source: a law keeps a term with no potential or current in it (``U + E``, ``I − J``).
    A resistor's parameter multiplies I; a controlled source's every term is one of its quantities."""
    cases, xs = _own(e.kind)
    if len(cases) != 1:  # (a textbook diode's drop is no source: it is one way of a non-linear element)
        return False
    (only,) = cases
    zero = {x: 0 for law in only.laws for x in sp.sympify(law).free_symbols if str(x).startswith("x_")} | dict.fromkeys(
        xs, 0
    )
    return any(sp.simplify(sp.sympify(law).subs(zero)) != 0 for law in only.laws)


# --------------------------------------------------------------------------------------- a circuit's relation


@dataclass(frozen=True)
class Symbols:
    """The circuit's quantities as the relation's variables."""

    net: Netlist
    labels: tuple[str, ...]  # each element's, in the netlist's order
    potentials: tuple[sp.Expr, ...]  # each point's (0: a reference)

    def index(self, e: Element) -> int:
        return next(k for k, (x, _) in enumerate(self.net.parts) if x is e)

    def currents(self, k: int) -> dict[str, sp.Expr]:
        """Into element ``k`` at each terminal: a variable for all but its last, which is minus their sum
        (charge kept, by construction)."""
        e, _ = self.net.parts[k]
        ts = e.kind.terminals
        own = {t: sp.Symbol(f"I_{self.labels[k]}" if len(ts) == 2 else f"I_{self.labels[k]}_{t}") for t in ts[:-1]}
        return {**own, ts[-1]: -sp.Add(*own.values())}

    def terminals(self, k: int) -> Terminals:
        e, ns = self.net.parts[k]
        label = self.labels[k]
        return Terminals(
            dict(zip(e.kind.terminals, (self.potentials[n] for n in ns), strict=True)),
            self.currents(k),
            lambda name: sp.Symbol(f"{name}_{label}"),
        )

    def param(self, e: Element, which: str = "") -> sp.Symbol:
        base = e.name or self.labels[self.index(e)]
        return sp.Symbol(base if not which else f"{which}_{base}")

    def params(self, e: Element) -> dict[str, sp.Symbol]:
        return {w: self.param(e, w) for w in e.kind.parameters}

    def V(self, p: Node | Net) -> sp.Expr:
        return self.potentials[next(n for n, q in self.net.named if q == p)]

    def of(self, q: Quantity) -> sp.Expr:
        match q:
            case Current(e, at):
                return self.currents(self.index(e))[at or e.kind.terminals[0]]
            case Voltage(e):
                t = self.terminals(self.index(e))
                return t.V[e.kind.terminals[0]] - t.V[e.kind.terminals[1]]
            case Parameter(e, which):
                return self.param(e, which)
            case Potential(p):
                return self.V(p)
            case Across(a, b):
                return self.V(a) - self.V(b)
        raise TypeError(q)


@cache
def symbols(c: Circuit) -> Symbols:
    net = netlist(c)
    # labels: an element's name when it is the only one so named, else its prefix and number
    names = [e.name for e, _ in net.parts]
    labels = tuple(
        e.name if e.name and names.count(e.name) == 1 else f"{e.kind.prefix}{k + 1}"
        for k, (e, _) in enumerate(net.parts)
    )
    # references: ground, else one point of each piece not on ground
    piece = list(range(net.size))

    def find(x: int) -> int:
        while piece[x] != x:
            x = piece[x]
        return x

    for _, ns in net.parts:
        for n in ns[1:]:
            piece[find(n)] = find(ns[0])
    grounded = {n for n, p in net.named if p == GND}
    roots = {find(n) for n in range(net.size)} - {find(n) for n in grounded}
    references = grounded | {min(n for n in range(net.size) if find(n) == r) for r in roots}
    # a point's symbol: its label (a net's name) when no other point shows the same, else its number
    shown = {n: p.name if isinstance(p, Net) else p.label for n, p in net.named}
    taken = list(shown.values())
    potentials = tuple(
        sp.Integer(0)
        if n in references
        else sp.Symbol(f"V_{shown[n]}" if shown.get(n) and taken.count(shown[n]) == 1 else f"V_{n}")
        for n in range(net.size)
    )
    return Symbols(net, labels, potentials)


def network(
    s: Symbols, parts: Sequence[int], points: Sequence[int], inflow: Mapping[int, sp.Expr] | None = None
) -> Relation:
    """The relation of elements ``parts`` (their indices) meeting at ``points``: each element's laws, and
    at each point Kirchhoff's current law — what flows into it from outside (``inflow``; none: nothing)
    is what flows on into the elements there."""
    inflow = inflow or {}
    laws: list[Equation] = []
    choices: list[tuple[Way, ...]] = []
    for k in parts:
        e = s.net.parts[k][0]
        cases = ways(e.kind.laws(s.terminals(k), s.params(e)))
        if len(cases) == 1:
            laws += [Equation(sp.sympify(x), Origin("law", e, i)) for i, x in enumerate(cases[0].laws)]
        else:
            choices.append(
                tuple(
                    Way(
                        e,
                        c.name,
                        tuple(Equation(sp.sympify(x), Origin("law", e, i, c.name)) for i, x in enumerate(c.laws)),
                        tuple(sp.sympify(h) for h in c.holds),
                    )
                    for c in cases
                )
            )
    kcl = []
    for n in points:
        into = [
            s.currents(k)[t]
            for k in parts
            for t, m in zip(s.net.parts[k][0].kind.terminals, s.net.parts[k][1], strict=True)
            if m == n
        ]
        kcl.append(Equation(sp.Add(*into) - inflow.get(n, sp.Integer(0)), Origin("kcl", n)))
    return Relation((), tuple(laws + kcl), tuple(choices))


def relation(c: Circuit) -> Relation:
    """The circuit as one relation (closed: nothing seen from outside)."""
    s = symbols(c)
    return network(s, range(len(s.net.parts)), [n for n in range(s.net.size) if s.potentials[n] != 0])


@dataclass(frozen=True)
class System:
    equations: tuple[Equation, ...]  # each = 0, read by an analysis, the data in
    unknowns: tuple[sp.Symbol, ...]
    symbols: Symbols
    choices: tuple[tuple[Way, ...], ...] = ()  # (read and with the data in too)


def equations(problem: Problem, analysis: Analysis, sources: sp.Expr | int = 1) -> System:
    """The problem's equations read by ``analysis``, its data in. ``sources``: what every independent
    source is scaled by (1: as given; 0…1: on the way up from nothing — for Newton, see ``solve``)."""
    s = symbols(problem.circuit)
    values: dict[sp.Symbol, sp.Expr] = {}
    for e, _ in s.net.parts:  # (a part's own: what a parameter is when nothing is given)
        for which, default in e.kind.defaults:
            values[s.param(e, which)] = cast(sp.Expr, parse(default))
    conditions: list[Equation] = []
    for key, value in problem.given.items():
        if value is UNKNOWN:
            continue
        match key:
            case Element() if isinstance(value, Mapping):
                values |= {s.param(key, w): cast(sp.Expr, x) for w, x in value.items() if x is not UNKNOWN}
            case Element():
                values[s.param(key)] = cast(sp.Expr, value)
            case str():
                values[sp.Symbol(key)] = cast(sp.Expr, value)
            case _:
                conditions.append(Equation(s.of(key) - cast(sp.Expr, value), Origin("given", key)))
    if sources != 1:
        for e, _ in s.net.parts:
            if is_source(e):
                for p in s.params(e).values():
                    if p in values:
                        values[p] = sources * values[p]
    rel = relation(problem.circuit)

    def read(eq: Equation) -> Equation:
        return Equation(subs(interpret(eq.expr, analysis), values), eq.origin)

    eqs = tuple(read(eq) for eq in (*rel.equations, *conditions))
    choices = tuple(
        tuple(
            Way(
                w.element,
                w.name,
                tuple(read(eq) for eq in w.equations),
                tuple(subs(interpret(h, analysis), values) for h in w.holds),
            )
            for w in choice
        )
        for choice in rel.choices
    )
    params = {p for e, _ in s.net.parts for p in s.params(e).values()} - set(values)
    found = {x for eq in eqs for x in _symbols_in(eq.expr)} | {
        x for choice in choices for w in choice for eq in w.equations for x in _symbols_in(eq.expr)
    }
    in_data = {x for v in values.values() for x in _symbols_in(sp.sympify(v))}  # (a value "R": a symbol)
    unknowns = (found - in_data - {TIME} - {x for x in found if x.name.endswith("⁻")}) | (params & found)
    return System(eqs, tuple(sorted(unknowns, key=str)), s, choices)


# --------------------------------------------------------------------------------------- solve


@dataclass(frozen=True)
class SolutionStep:
    """One step: what was found, its value, and from which equations (their origins: the reason)."""

    found: tuple[sp.Symbol, ...]
    values: tuple[sp.Expr, ...]
    because: tuple[Origin, ...]
    how: str = "alone"  # "alone" (one equation, one unknown), "together" (several at once), "numerically",
    # "assumed" (an element taken to be one of its ways), "checked" (what that way needs holds), "rejected"


@dataclass(frozen=True)
class Solution:
    problem: Problem
    values: Mapping[sp.Symbol, sp.Expr]
    unknowns: frozenset[sp.Symbol]
    symbols: Symbols
    steps: tuple[SolutionStep, ...] = ()

    def __call__(self, q: Quantity) -> sp.Expr:
        value = sp.simplify(subs(self.symbols.of(q), self.values))
        if value.free_symbols & self.unknowns:  # (still in what was not found)
            raise Undetermined(q)
        return value

    @property
    def answers(self) -> dict[Quantity, sp.Expr]:
        return {q: self(q) for q in self.problem.find}


def _steps(system: System) -> tuple[dict[sp.Symbol, sp.Expr], tuple[SolutionStep, ...]]:
    """Solved as one does by hand: an equation with one unknown left at a time (its origin the reason);
    when none is left, what remains together."""
    known: dict[sp.Symbol, sp.Expr] = {}
    pending = list(system.equations)
    unknown = set(system.unknowns)
    out: list[SolutionStep] = []
    while pending:
        for eq in pending:
            expr = subs(eq.expr, known)
            left = _symbols_in(expr) & unknown
            if len(left) <= 1:
                pending.remove(eq)
                if left:
                    (x,) = left
                    roots = sp.solve(expr, x)
                    if len(roots) == 1:
                        known[x] = sp.simplify(roots[0])
                        unknown.discard(x)
                        out.append(SolutionStep((x,), (known[x],), (eq.origin,)))
                break
        else:  # nothing with one unknown: the rest together (a loop's equations, say)
            rest = sorted({x for eq in pending for x in _symbols_in(subs(eq.expr, known))} & unknown, key=str)
            found = sp.solve([subs(eq.expr, known) for eq in pending], rest, dict=True)
            if not found:
                raise Undetermined("no solution: the data contradict each other")
            together = {x: sp.simplify(v) for x, v in found[0].items()}
            known |= together
            unknown -= set(together)
            origins = tuple(eq.origin for eq in pending)
            out.append(SolutionStep(tuple(together), tuple(together.values()), origins, "together"))
            known = {x: sp.simplify(subs(v, known)) for x, v in known.items()}
            break
    return known, tuple(out)


class NotLinear(ValueError):
    """What is asked holds only for a linear circuit (a phasor, superposition); an element's law is not."""


def _algebraic(system: System) -> bool:
    """Polynomial in its unknowns (an unknown resistance times a current too): algebra solves it."""
    try:
        for eq in system.equations:
            sp.Poly(eq.expr, *system.unknowns)
        return True
    except sp.PolynomialError:  # (exp of an unknown: a diode's)
        return False


def solve(problem: Problem, analysis: DC | AC | None = None) -> Solution:
    """Where it settles (DC), or its phasors at ``AC(ω)`` — and the steps there. Linear: by algebra, step
    by step; beyond algebra (a diode's exp): by Newton, every value needed, the sources raised from nothing."""
    analysis = analysis or DC()
    rel = relation(problem.circuit)
    if any(sp.sympify(eq.expr).has(Pre) for eq in rel.equations) or any(
        sp.sympify(eq.expr).has(Pre) for c in rel.choices for w in c for eq in w.equations
    ):  # (where it settles is what came before it: a flip-flop holds what it was last given)
        raise Undetermined("it has memory — what it holds depends on what came before: simulate it")
    system = equations(problem, analysis)
    if any(eq.expr.has(TIME) for eq in system.equations):
        raise Undetermined("its data change in time: simulate it")
    if system.choices:
        return _by_cases(problem, system)
    if _algebraic(system):
        values, steps = _steps(system)
        return Solution(problem, values, frozenset(system.unknowns) - set(values), system.symbols, steps)
    if isinstance(analysis, AC):
        raise NotLinear("a phasor of a non-linear circuit: around its working point (not yet)")
    lam = sp.Symbol("λ")
    raised = equations(problem, analysis, sources=lam)
    exprs = [eq.expr for eq in raised.equations]
    unknowns = list(raised.unknowns)
    if any(x not in {*unknowns, lam} for e in exprs for x in _symbols_in(e)):
        raise Undetermined("a non-linear circuit is solved with every value given")
    f, j = compiled(exprs, unknowns, (lam,))
    found = homotopy(f, j, len(unknowns))
    if found is None:
        raise Undetermined("Newton did not get there")
    values = {u: sp.Float(v) for u, v in zip(unknowns, found, strict=True)}
    origins = tuple(eq.origin for eq in raised.equations)
    step = SolutionStep(tuple(values), tuple(values.values()), origins, "numerically")
    return Solution(problem, values, frozenset(), raised.symbols, (step,))


def _by_cases(problem: Problem, system: System) -> Solution:
    """An element of several ways (a textbook diode): as one solves it by hand — assume a way for each,
    solve, check that what each way needs holds; if not, the next assumption. The tries are the steps."""
    tried: list[SolutionStep] = []
    good: list[Solution] = []
    for combo in itertools.product(*system.choices):
        assumed = [SolutionStep((), (), (Origin("assumed", w.element, case=w.name),), "assumed") for w in combo]
        within = System(
            system.equations + tuple(eq for w in combo for eq in w.equations), system.unknowns, system.symbols
        )
        try:
            values, steps = _steps(within)
        except Undetermined:  # (no circuit at all that way: contradicts itself)
            tried += [
                *assumed,
                SolutionStep((), (), (Origin("holds", combo[0].element, case=combo[0].name),), "rejected"),
            ]
            continue
        checks = [(w, sp.simplify(subs(h, values))) for w in combo for h in w.holds]
        if any(_symbols_in(v) & set(system.unknowns) for _, v in checks):
            continue  # (that way leaves part of the circuit floating — nothing decides it: not this way)
        if any(not v.is_number for _, v in checks):
            raise Undetermined("which way each element is depends on values not given")
        broken = [(w, v) for w, v in checks if float(v) < -1e-12]
        if broken:
            w, _ = broken[0]
            tried += [*assumed, *steps, SolutionStep((), (), (Origin("holds", w.element, case=w.name),), "rejected")]
            continue
        checked = [SolutionStep((), (), (Origin("holds", w.element, case=w.name),), "checked") for w in combo]
        unknown = frozenset(system.unknowns) - set(values)
        good.append(Solution(problem, values, unknown, system.symbols, (*tried, *assumed, *steps, *checked)))
    if not good:
        raise Undetermined("no way of its elements fits")
    if len(good) > 1:  # (a latch: two states — a circuit with memory, not a single answer)
        raise Undetermined("more than one way fits")
    return good[0]


# --------------------------------------------------------------------------------------- a piece seen from its ends

PORT_U, PORT_I = sp.symbols("U_port I_port")  # a two-ended piece's: the drop from its first end to its
# second, the current in at its first end (out at its second) — as a two-terminal element's U and I


class NotOnePort(ValueError):
    """A black box here is of a piece with one free end each side (1 → 1)."""


def port(s: Symbols, parts: Sequence[int], a: int, b: int, analysis: Analysis) -> Relation | None:
    """Elements ``parts`` between points ``a`` and ``b`` as one relation of ``PORT_U``, ``PORT_I``:
    everything else inside eliminated (the black box). None: no single relation."""
    points = sorted({n for k in parts for n in s.net.parts[k][1]} | {a, b})
    ref = s.potentials[b]
    zero: dict[sp.Symbol, sp.Expr] = {ref: sp.Integer(0)} if isinstance(ref, sp.Symbol) else {}
    inside = network(s, parts, [n for n in points if n != b], {a: PORT_I})
    eqs = [subs(interpret(eq.expr, analysis), zero) for eq in inside.equations]
    eqs.append(PORT_U - subs(s.potentials[a], zero))
    params = {p for k in parts for p in s.params(s.net.parts[k][0]).values()}
    inner = sorted({x for eq in eqs for x in _symbols_in(eq)} - params - {PORT_U, PORT_I}, key=str)
    for var in (PORT_U, PORT_I):  # U from I (most pieces); I from U (a current source: U is free)
        found = sp.solve(eqs, [*inner, var], dict=True)
        if len(found) == 1 and var in found[0]:
            return Relation((PORT_U, PORT_I), (Equation(sp.simplify(var - found[0][var]), Origin("port", (a, b))),))
    return None


def blackbox(piece: Circuit, analysis: Analysis | None = None) -> Relation | None:
    """A 1 → 1 piece seen from its ends (the elements' own names as their parameters)."""
    net = netlist(piece)
    if free(piece) != (1, 1) or len(net.left) != 1:
        raise NotOnePort(free(piece))
    s = Symbols(
        net,
        tuple(e.name or e.kind.prefix for e, _ in net.parts),
        tuple(sp.Symbol(f"v{n}") for n in range(net.size)),
    )
    return port(s, range(len(net.parts)), net.left[0], net.right[0], analysis or DC())


def matches(relation: Relation, kind: Kind, analysis: Analysis | None = None) -> sp.Expr | None:
    """The parameter that makes one element of ``kind`` this very relation (two resistors in series: a
    resistor of R₁ + R₂ — found, not told), or None."""
    p = sp.Symbol("p_match")
    its = blackbox(Element(kind, p.name), analysis) if len(kind.terminals) == 2 else None
    if its is None or len(relation.equations) != 1:
        return None
    for var, other in ((PORT_U, PORT_I), (PORT_I, PORT_U)):
        mine, theirs = sp.solve(relation.equations[0].expr, var), sp.solve(its.equations[0].expr, var)
        if len(mine) != 1 or len(theirs) != 1:
            continue
        rest = sp.numer(sp.together(sp.expand(mine[0] - theirs[0])))
        coeffs = sp.Poly(rest, other).all_coeffs() if rest.has(other) else [rest]
        # every coefficient zero, whatever ``other`` is: those without p must already be
        if any(not c.has(p) and sp.simplify(c) != 0 for c in coeffs):
            return None
        found = sp.solve([c for c in coeffs if c.has(p)], p, dict=True)
        if len(found) == 1 and p in found[0]:
            return sp.simplify(found[0][p])
        return None
    return None


# --------------------------------------------------------------------------------------- simulate


class NoConvergence(ArithmeticError):
    """A step in time Newton could not take (at ``t``)."""


@dataclass(frozen=True)
class State:
    t: float
    values: Mapping[sp.Symbol, float]  # every unknown then: where the next step starts, what it remembers
    way: int = 0  # which combination of its elements' ways it was in (a textbook diode on or off)


@dataclass(frozen=True)
class Stepper:
    """One step in time, one way of its elements, compiled: the equations of a step, the previous
    state's quantities in them."""

    unknowns: tuple[sp.Symbol, ...]
    f: Residual = field(repr=False)
    j: Jacobian = field(repr=False)
    holds: tuple[sp.Expr, ...]  # what that way needs (≥ 0)


@dataclass(frozen=True)
class Stepping:
    dt: float
    remembered: tuple[sp.Expr, ...]  # what each x⁻ is (a quantity of the state before)
    ways: int  # how many combinations of its elements' ways
    stepper: Callable[[int], Stepper] = field(repr=False)  # (each compiled when first needed)


def compile_steps(problem: Problem, dt: float) -> Stepping:
    lam = sp.Symbol("λ")
    system = equations(problem, Step(sp.Float(dt)), sources=lam)
    # what a step remembers: each x under D or Pre, a step ago (x⁻)
    rel = relation(problem.circuit)
    held: list[sp.Expr] = sorted(
        {
            cast(sp.Expr, a.args[0])
            for eq in (*rel.equations, *(eq for c in rel.choices for w in c for eq in w.equations))
            for a in sp.sympify(eq.expr).atoms(D, Pre)
        },
        key=str,
    )
    before_of = [before(x) for x in held]
    combos = list(itertools.product(*system.choices))

    @cache
    def stepper(k: int) -> Stepper:
        exprs = [eq.expr for eq in system.equations] + [eq.expr for w in combos[k] for eq in w.equations]
        unknowns = [u for u in system.unknowns if u not in before_of]
        if any(x not in {*unknowns, lam, TIME, *before_of} for e in exprs for x in _symbols_in(e)):
            raise Undetermined("a step in time needs every value")
        f, j = compiled(exprs, unknowns, (lam, TIME, *before_of))
        return Stepper(tuple(unknowns), f, j, tuple(h for w in combos[k] for h in w.holds))

    return Stepping(dt, tuple(held), len(combos), stepper)


def step(stepping: Stepping, state: State) -> State:
    """The circuit ``dt`` on — from the last state, in the way it was if that still holds, else the next
    way that does (and if Newton does not get there, the sources raised)."""
    first = stepping.stepper(state.way)
    at = {**dict.fromkeys(first.unknowns, 0.0), **state.values}  # (at rest before the first step)
    prev = [float(subs(sp.sympify(x), at)) for x in stepping.remembered]
    for k in (state.way, *(k for k in range(stepping.ways) if k != state.way)):
        s = stepping.stepper(k)
        guess = [at.get(u, 0.0) for u in s.unknowns]
        now = state.t + stepping.dt
        x = (
            newton(s.f, s.j, guess, (1.0, now, *prev))
            or newton(s.f, s.j, guess, (1.0, now, *prev), damped=False)  # (across a jump: logic)
            or homotopy(s.f, s.j, len(guess), (now, *prev), guess)
        )
        if x is None:
            continue
        values = dict(zip(s.unknowns, x, strict=True))
        if all(
            float(subs(h, {**values, TIME: now, **dict(zip(map(before, stepping.remembered), prev))})) >= -1e-9
            for h in s.holds
        ):
            return State(state.t + stepping.dt, values, k)
    raise NoConvergence(state.t + stepping.dt)


@dataclass(frozen=True)
class Trace:
    problem: Problem
    states: tuple[State, ...]
    symbols: Symbols

    def __call__(self, q: Quantity) -> Callable[[float], float]:
        """``q`` in time: a function of t (the nearest step)."""
        x = sp.sympify(self.symbols.of(q))
        ys = [float(subs(x, s.values)) for s in self.states]

        def at(t: float) -> float:
            return ys[min(range(len(self.states)), key=lambda i: abs(self.states[i].t - t))]

        return at


def simulate(problem: Problem, until: float, dt: float | None = None) -> Trace:
    """From rest (every capacitor empty, every inductor still) for ``until`` seconds: ``step`` unfolded."""
    stepping = compile_steps(problem, dt or until / 1000)
    states = [State(0.0, {})]
    while states[-1].t < until - 1e-12:
        states.append(step(stepping, states[-1]))
    return Trace(problem, tuple(states[1:]), symbols(problem.circuit))
