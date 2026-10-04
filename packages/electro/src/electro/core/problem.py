"""A problem as one is set — a closed circuit, what is given, what is sought — and what answers it:
``solve`` (DC, or phasors at ω) and ``simulate`` (in time). Each analysis is only a reading of ``D``:
DC: 0, AC: jω, a step in time: the difference back to the step before. Pure functions throughout
(sympy and a stepping loop inside, nothing shared).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from functools import cache
from types import MappingProxyType
from typing import cast

import sympy as sp

from electro.values import UNKNOWN, parse

from .syntax import GND, Circuit, D, Element, Net, Netlist, Node, is_closed, netlist

# sympy's own types are loose (``subs`` of a dict, ``replace`` gives ``Basic``): said once, here


def _subs(x: sp.Expr, values: Mapping[sp.Symbol, sp.Expr] | Mapping[sp.Symbol, float]) -> sp.Expr:
    return cast(sp.Expr, x.subs(list(values.items())))


def _replace(x: sp.Expr, f: Callable[[sp.Expr], sp.Expr]) -> sp.Expr:
    return cast(sp.Expr, x.replace(D, f))


def _symbols_in(x: sp.Expr) -> set[sp.Symbol]:
    return {s for s in x.free_symbols if isinstance(s, sp.Symbol)}


# --------------------------------------------------------------------------------------- quantities


@dataclass(frozen=True)
class Current:
    of: Element


@dataclass(frozen=True)
class Voltage:
    of: Element


@dataclass(frozen=True)
class Parameter:
    of: Element  # its value


@dataclass(frozen=True)
class Potential:
    at: Node | Net


@dataclass(frozen=True)
class Across:
    a: Node | Net
    b: Node | Net  # V_a − V_b


Quantity = Current | Voltage | Parameter | Potential | Across


def I(e: Element) -> Current:  # noqa: E743 — as a book writes it
    return Current(e)


def U(a: Element | Node | Net, b: Node | Net | None = None) -> Voltage | Across:
    return Voltage(a) if isinstance(a, Element) else Across(a, b if b is not None else GND)


def V(p: Node | Net) -> Potential:
    return Potential(p)


# --------------------------------------------------------------------------------------- problem


class NotClosed(ValueError):
    """Only a circuit with nothing left to connect is a problem (a piece: ``equivalent``)."""


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
        # (read once, as it is built — values parsed, nothing to change it after)
        object.__setattr__(self, "given", MappingProxyType({k: parse(v) for k, v in self.given.items()}))
        object.__setattr__(self, "find", tuple(self.find))
        if not is_closed(self.circuit):
            raise NotClosed()
        names = {e.name for e, _, _ in netlist(self.circuit).parts}
        for k in self.given:
            if isinstance(k, str) and k not in names:
                raise NoSuchParameter(k)

    @property
    def values(self) -> Mapping[Key, sp.Expr]:
        """What is given, each a value (an unknown left out)."""
        return {k: cast(sp.Expr, v) for k, v in self.given.items() if v is not UNKNOWN}


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


def before(x: sp.Symbol) -> sp.Symbol:
    """``x`` a step ago (what a step in time remembers)."""
    return sp.Symbol(f"{x.name}⁻")


def interpret(law: sp.Expr, analysis: Analysis) -> sp.Expr:
    """An element's law in an analysis: ``D`` read as it reads it."""
    match analysis:
        case DC():
            return _replace(law, lambda x: sp.Integer(0))
        case AC(omega):
            return _replace(law, lambda x: sp.I * omega * x)
        case Step(dt):
            return _replace(law, lambda x: (x - before(cast(sp.Symbol, x))) / dt)
    raise TypeError(analysis)


# --------------------------------------------------------------------------------------- equations


@dataclass(frozen=True)
class Symbols:
    """The circuit's quantities as the solver's symbols."""

    net: Netlist
    labels: tuple[str, ...]  # each element's, in the netlist's order
    potentials: tuple[sp.Expr, ...]  # each point's (0: a reference)

    def element(self, e: Element) -> int:
        return next(k for k, (x, _, _) in enumerate(self.net.parts) if x is e)

    def U(self, e: Element) -> sp.Symbol:
        return sp.Symbol(f"U_{self.labels[self.element(e)]}")

    def I(self, e: Element) -> sp.Symbol:  # noqa: E743
        return sp.Symbol(f"I_{self.labels[self.element(e)]}")

    def param(self, e: Element) -> sp.Symbol:
        return sp.Symbol(e.name or self.labels[self.element(e)])

    def V(self, p: Node | Net) -> sp.Expr:
        return self.potentials[next(n for n, q in self.net.named if q == p)]

    def of(self, q: Quantity) -> sp.Expr:
        match q:
            case Current(e):
                return self.I(e)
            case Voltage(e):
                return self.U(e)
            case Parameter(e):
                return self.param(e)
            case Potential(p):
                return self.V(p)
            case Across(a, b):
                return self.V(a) - self.V(b)
        raise TypeError(q)


@cache
def symbols(c: Circuit) -> Symbols:
    net = netlist(c)
    # labels: an element's name when it is the only one so named, else its prefix and number
    names = [e.name for e, _, _ in net.parts]
    labels = tuple(
        e.name if e.name and names.count(e.name) == 1 else f"{e.kind.prefix}{k + 1}"
        for k, (e, _, _) in enumerate(net.parts)
    )
    # references: ground, else one point of each piece not on ground
    piece = list(range(net.size))

    def find(x: int) -> int:
        while piece[x] != x:
            x = piece[x]
        return x

    for _, a, b in net.parts:
        piece[find(a)] = find(b)
    grounded = {n for n, p in net.named if p == GND}
    roots_grounded = {find(n) for n in grounded}
    references = grounded | {
        min(n for n in range(net.size) if find(n) == r) for r in {find(n) for n in range(net.size)} - roots_grounded
    }
    # a point's symbol: its label (a net's name) when no other point shows the same, else its number —
    # a label only shows, two points labelled alike are still two
    shown = {n: p.name if isinstance(p, Net) else p.label for n, p in net.named}
    taken = list(shown.values())
    potentials = tuple(
        sp.Integer(0)
        if n in references
        else sp.Symbol(f"V_{shown[n]}" if shown.get(n) and taken.count(shown[n]) == 1 else f"V_{n}")
        for n in range(net.size)
    )
    return Symbols(net, labels, potentials)


@dataclass(frozen=True)
class System:
    equations: tuple[sp.Expr, ...]  # each = 0
    unknowns: tuple[sp.Symbol, ...]
    symbols: Symbols


def equations(problem: Problem, analysis: Analysis) -> System:
    """Kirchhoff (from how the points are glued) and each element's law read by the analysis; what is
    given: a parameter's value, or a condition on a quantity."""
    s = symbols(problem.circuit)
    net = s.net
    laws = [interpret(e.kind.law(s.U(e), s.I(e), s.param(e)), analysis) for e, _, _ in net.parts]
    drops = [s.U(e) - (s.potentials[a] - s.potentials[b]) for e, a, b in net.parts]
    kcl = [
        sp.Add(*(s.I(e) for e, a, _ in net.parts if a == n), *(-s.I(e) for e, _, b in net.parts if b == n))
        for n in range(net.size)
        if s.potentials[n] != 0
    ]
    values: dict[sp.Symbol, sp.Expr] = {}
    conditions: list[sp.Expr] = []
    for key, value in problem.values.items():
        match key:
            case Element():
                values[s.param(key)] = value
            case str():
                values[sp.Symbol(key)] = value
            case _:
                conditions.append(s.of(key) - value)
    params = {s.param(e) for e, _, _ in net.parts} - set(values)
    unknowns = (
        [s.U(e) for e, _, _ in net.parts]
        + [s.I(e) for e, _, _ in net.parts]
        + [p for p in s.potentials if isinstance(p, sp.Symbol)]
        + sorted(params, key=str)
    )
    eqs = tuple(_subs(sp.sympify(x), values) for x in laws + drops + kcl + conditions)
    return System(eqs, tuple(unknowns), s)


# --------------------------------------------------------------------------------------- solve


@dataclass(frozen=True)
class Solution:
    problem: Problem
    values: Mapping[sp.Symbol, sp.Expr]
    unknowns: frozenset[sp.Symbol]
    symbols: Symbols

    def __call__(self, q: Quantity) -> sp.Expr:
        value = sp.simplify(_subs(self.symbols.of(q), self.values))
        if value.free_symbols & self.unknowns:  # (still in what was not found)
            raise Undetermined(q)
        return value

    @property
    def answers(self) -> dict[Quantity, sp.Expr]:
        return {q: self(q) for q in self.problem.find}


def solve(problem: Problem, analysis: DC | AC | None = None) -> Solution:
    """Where it settles (DC), or its phasors at ``AC(ω)``."""
    system = equations(problem, analysis or DC())
    found = sp.solve(system.equations, system.unknowns, dict=True)
    if not found:
        raise Undetermined("no solution: the data contradict each other")
    return Solution(problem, found[0], frozenset(system.unknowns), system.symbols)


# --------------------------------------------------------------------------------------- simulate


@dataclass(frozen=True)
class State:
    t: float
    remembered: Mapping[sp.Symbol, float]  # what the last step left (x⁻ for each x under D)


@dataclass(frozen=True)
class Stepper:
    """One step in time, compiled once: the next state's quantities from the last one's."""

    dt: float
    unknowns: tuple[sp.Symbol, ...]
    remembers: tuple[sp.Symbol, ...]  # the x whose x⁻ the next step needs
    next: Callable[..., Sequence[float]] = field(repr=False)  # remembered values -> the unknowns' values


def compile_steps(problem: Problem, dt: float) -> Stepper:
    system = equations(problem, Step(sp.Float(dt)))
    remembered = sorted({x for eq in system.equations for x in _symbols_in(eq) if x.name.endswith("⁻")}, key=str)
    found = sp.solve(system.equations, system.unknowns, dict=True)
    if len(found) != 1:
        raise Undetermined("a step in time needs every value")
    exprs = [found[0].get(u, u) for u in system.unknowns]
    return Stepper(
        dt,
        system.unknowns,
        tuple(sp.Symbol(x.name[:-1]) for x in remembered),
        sp.lambdify(remembered, exprs, "math"),
    )


def step(stepper: Stepper, state: State) -> tuple[State, dict[sp.Symbol, float]]:
    """The circuit ``dt`` on: the new state, and every quantity at its end."""
    values = dict(
        zip(stepper.unknowns, stepper.next(*(state.remembered.get(x, 0.0) for x in stepper.remembers)), strict=True)
    )
    return State(state.t + stepper.dt, {x: float(values[x]) for x in stepper.remembers}), values


@dataclass(frozen=True)
class Trace:
    problem: Problem
    times: tuple[float, ...]
    rows: tuple[Mapping[sp.Symbol, float], ...]
    symbols: Symbols

    def __call__(self, q: Quantity):
        """``q`` in time: a function of t (linear between the steps)."""
        x = self.symbols.of(q)
        ys = [float(_subs(sp.sympify(x), row)) for row in self.rows]

        def at(t: float) -> float:
            k = min(range(len(self.times)), key=lambda i: abs(self.times[i] - t))
            return ys[k]

        return at


def simulate(problem: Problem, until: float, dt: float | None = None) -> Trace:
    """From rest (every capacitor empty, every inductor still) for ``until`` seconds."""
    stepper = compile_steps(problem, dt or until / 1000)
    state = State(0.0, {})
    times: list[float] = []
    rows: list[Mapping[sp.Symbol, float]] = []
    while state.t < until - 1e-12:
        state, values = step(stepper, state)
        times.append(state.t)
        rows.append(values)
    return Trace(problem, tuple(times), tuple(rows), symbols(problem.circuit))
