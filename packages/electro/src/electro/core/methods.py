"""Textbook methods as roads through the same equations — no law of their own (DESIGN.md §12).

Each takes what the engine offers (``solve``, ``port``, ``matches``) and the elements' laws as they are:
whether a method may be used (linear? which elements are independent sources?) is read off the laws, and
the rules of simplifying (series, parallel, sources in series) are found by computing, not written down.
"""

from __future__ import annotations

import cmath
import math
import random
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from typing import cast

import sympy as sp

from electro.values import parse

from .problem import (
    AC,
    DC,
    PORT_I,
    PORT_U,
    Analysis,
    Current,
    Equation,
    Key,
    NotLinear,
    Parameter,
    Problem,
    Quantity,
    Relation,
    Solution,
    Undetermined,
    Voltage,
    is_linear,
    is_source,
    matches,
    port,
    solve,
    subs,
    symbols,
)
from .syntax import (
    GND,
    KINDS,
    CurrentSource,
    Element,
    Net,
    Node,
    Open,
    Resistor,
    VoltageSource,
    Wire,
    netlist,
    rebuild,
)

# --------------------------------------------------------------------------------------- what the laws say


# --------------------------------------------------------------------------------------- superposition


@dataclass(frozen=True)
class Superposition:
    quantity: Quantity
    parts: tuple[tuple[Element, sp.Expr], ...]  # each source alone (the others' parameters zero): its share
    total: sp.Expr


def superposition(problem: Problem, q: Quantity, analysis: DC | AC | None = None) -> Superposition:
    """``q`` as the sum of what each independent source makes of it alone."""
    elements = [e for e, _ in netlist(problem.circuit).parts]
    for e in elements:
        if not is_linear(e, analysis):
            raise NotLinear(e)
    sources = [e for e in elements if is_source(e)]
    parts = tuple(
        (s, solve(Problem(problem.circuit, {**problem.given, **{o: 0 for o in sources if o is not s}}), analysis)(q))
        for s in sources
    )
    return Superposition(q, parts, sp.simplify(sp.Add(*(v for _, v in parts))))


# --------------------------------------------------------------------------------------- simplifying


@dataclass(frozen=True)
class Reduction:
    """One step: two elements replaced by one that the two are, seen from where they meet the rest."""

    how: str  # "series" | "parallel" (read off the shape: one point between them, or the same two)
    replaced: tuple[Element, Element]
    by: Element
    value: sp.Expr  # its parameter, in the replaced ones' (R₂·R₃₄/(R₂+R₃₄))
    amount: sp.Expr  # …with the data in (a number, when all of it is given)


def _combined(a: str, b: str) -> str:
    """A book's name for what two make: R_3 and R_4 → R_34 (else both side by side)."""
    (x, _, m), (y, _, n) = a.partition("_"), b.partition("_")
    return f"{x}_{m}{n}" if x == y and m and n else f"{a}{b}"


def _keeps(problem: Problem, keep: Collection[Element]) -> set[Element]:
    """What a step may not touch: what is asked about, what a condition speaks of, what was said."""
    held = set(keep)
    for q in (*problem.find, *(k for k in problem.given if not isinstance(k, (Element, str)))):
        if isinstance(q, (Current, Voltage, Parameter)):
            held.add(q.of)
    return held


def _step(problem: Problem, keep: Collection[Element], analysis: Analysis) -> tuple[Problem, Reduction] | None:
    s = symbols(problem.circuit)
    net = s.net
    held = _keeps(problem, keep)
    ends = [n for _, ns in net.parts for n in ns]
    named = dict(net.named)
    asked = {
        p
        for q in problem.find
        for p in (getattr(q, "at", None), getattr(q, "a", None), getattr(q, "b", None))
        if isinstance(p, (Node, Net))
    }
    # candidates: two elements meeting at a point nothing else touches (series), or on the same two (parallel)
    pairs: list[tuple[str, int, int, int, int, int]] = []  # how, i, j, outer a, outer b, the point between
    two = [(i, e, *ns) for i, (e, ns) in enumerate(net.parts) if len(ns) == 2]
    for i, e, a, b in two:
        for j, f, c, d in two:
            if j <= i or e in held or f in held:
                continue
            if {a, b} == {c, d} and a != b:
                pairs.append(("parallel", i, j, a, b, -1))
            for mid in {a, b} & {c, d}:
                if ends.count(mid) == 2 and named.get(mid) not in (GND, *asked) and len({a, b, c, d}) == 3:
                    outer = [n for n in (a, b) if n != mid] + [n for n in (c, d) if n != mid]
                    pairs.append(("series", i, j, outer[0], outer[1], mid))
    for how, i, j, a, b, _ in pairs:
        relation = port(s, (i, j), a, b, analysis)
        if relation is None:
            continue
        for kind in KINDS:  # (first that fits: a resistor before anything else — an impedance in AC)
            value = matches(relation, kind, analysis)
            if value is None:
                continue
            e, f = net.parts[i][0], net.parts[j][0]
            by = kind(_combined(s.labels[i], s.labels[j]))
            parts = [p for k, p in enumerate(net.parts) if k not in (i, j)] + [(by, (a, b))]
            known = {s.param(x): v for x, v in problem.values.items() if isinstance(x, Element)}
            known |= {sp.Symbol(x): v for x, v in problem.values.items() if isinstance(x, str)}
            names = {x.name for x, _ in parts}
            given = {
                k: v
                for k, v in problem.given.items()
                if k is not e and k is not f and not (isinstance(k, str) and k not in names)
            }
            amount = sp.simplify(subs(value, known))
            simpler = Problem(rebuild(parts, net.named), {**given, by: amount}, problem.find)
            return simpler, Reduction(how, (e, f), by, value, amount)
    return None


def simplify(
    problem: Problem, keep: Collection[Element] = (), analysis: DC | AC | None = None
) -> tuple[Problem, tuple[Reduction, ...]]:
    """The problem on a smaller circuit that behaves alike where it is asked about — and the steps there
    (the textbook's equivalent circuits). What is sought, and ``keep``, stays as it is."""
    steps: list[Reduction] = []
    while (found := _step(problem, keep, analysis or DC())) is not None:
        problem, reduction = found
        steps.append(reduction)
    return problem, tuple(steps)


# --------------------------------------------------------------------------------------- seen from two points


def between(problem: Problem, a: Node | Net, b: Node | Net, analysis: DC | AC | None = None) -> Relation | None:
    """The circuit as seen from two of its points — a current let in at ``a``, out at ``b`` — its data in."""
    s = symbols(problem.circuit)
    pa, pb = (next(n for n, q in s.net.named if q == x) for x in (a, b))
    values = {s.param(e): v for e, v in problem.values.items() if isinstance(e, Element)}
    relation = port(s, range(len(s.net.parts)), pa, pb, analysis or DC())
    if relation is None:
        return None
    return Relation(relation.ends, tuple(Equation(subs(eq.expr, values), eq.origin) for eq in relation.equations))


def resistance(relation: Relation | None, analysis: DC | AC | None = None) -> sp.Expr | None:
    """What one resistor (an impedance, in AC) a black box is, if it is one — from ``matches``, no rule of
    its own (series, parallel: found)."""
    return matches(relation, Resistor, analysis) if relation is not None else None


@dataclass(frozen=True)
class Thevenin:
    E: sp.Expr  # the voltage at its ends with nothing taken (open)
    Z: sp.Expr  # how it drops with the current taken


def thevenin(relation: Relation | None) -> Thevenin | None:
    """A black box as a source and a resistance: ``U = E − Z·I`` with I taken out of its first end."""
    if relation is None or len(relation.equations) != 1:
        return None
    us = sp.solve(relation.equations[0].expr, PORT_U)
    if len(us) != 1:
        return None
    u = sp.expand(us[0])
    return Thevenin(sp.simplify(u.subs(PORT_I, 0)), sp.simplify(u.diff(PORT_I)))


# --------------------------------------------------------------------------------------- a hole filled


@dataclass(frozen=True)
class Filled:
    """A problem with its hole filled: by what, and the solution with it."""

    problem: Problem
    by: Element
    solution: Solution


def fill(problem: Problem, hole: Element, analysis: DC | AC | None = None) -> Filled:
    """The simplest element that fits where ``hole`` is: a wire, a break, a resistor (never negative),
    a voltage source, a current source — the first that the data do not contradict and pin down."""
    s = symbols(problem.circuit)
    net = s.net
    for kind in (Wire, Open, Resistor, VoltageSource, CurrentSource):
        by = kind(hole.name)
        parts = [(by, ns) if e is hole else (e, ns) for e, ns in net.parts]
        given = {k: v for k, v in problem.given.items() if k is not hole}
        candidate = Problem(rebuild(parts, net.named), given, problem.find)
        try:
            solution = solve(candidate, analysis)
            for w in kind.parameters:  # (pinned down by the data, not left free)
                solution(Parameter(by, w))
        except Undetermined:
            continue
        return Filled(candidate, by, solution)
    raise Undetermined("no simple element fits where the hole is")


# --------------------------------------------------------------------------------------- over a range


@dataclass(frozen=True)
class Sweep:
    """What ``q`` comes to as one datum takes each value."""

    values: tuple[sp.Expr, ...]
    results: tuple[sp.Expr, ...]


def sweep(problem: Problem, key: Key, values: Sequence[object], q: Quantity, analysis: DC | AC | None = None) -> Sweep:
    results = tuple(
        solve(Problem(problem.circuit, {**problem.given, key: v}, problem.find), analysis)(q) for v in values
    )
    return Sweep(tuple(cast(sp.Expr, parse(v)) for v in values), results)


@dataclass(frozen=True)
class Response:
    """``q`` against the frequency, the source at 1 (its transfer function H): solved once, ω a letter."""

    f: tuple[float, ...]
    H: tuple[complex, ...]

    @property
    def gain_db(self) -> tuple[float, ...]:
        return tuple(20 * math.log10(max(abs(h), 1e-300)) for h in self.H)

    @property
    def phase_deg(self) -> tuple[float, ...]:
        return tuple(math.degrees(cmath.phase(h)) for h in self.H)

    def cutoffs(self) -> list[float]:
        """Where the gain crosses 3 dB under its largest (between two points: in log f, straight)."""
        g = self.gain_db
        level = max(g) - 3.0103
        out = []
        for k in range(len(g) - 1):
            if (g[k] - level) * (g[k + 1] - level) < 0:
                t = (level - g[k]) / (g[k + 1] - g[k])
                out.append(10 ** (math.log10(self.f[k]) + t * (math.log10(self.f[k + 1]) - math.log10(self.f[k]))))
        return out


def respond(
    problem: Problem, q: Quantity, source: Element, f: tuple[float, float] = (10, 1e6), points: int = 200
) -> Response:
    omega = sp.Symbol("omega", positive=True)
    h = solve(Problem(problem.circuit, {**problem.given, source: 1}), AC(omega))(q)
    at = sp.lambdify(omega, h, "cmath")
    lo, hi = math.log10(f[0]), math.log10(f[1])
    fs = tuple(10 ** (lo + (hi - lo) * k / (points - 1)) for k in range(points))
    return Response(fs, tuple(complex(at(2 * math.pi * x)) for x in fs))


@dataclass(frozen=True)
class Spread:
    """What ``q`` came to in each build of the circuit, its parts within their tolerances."""

    values: tuple[float, ...]

    def stats(self) -> dict[str, float]:
        n = len(self.values)
        mean = sum(self.values) / n
        std = math.sqrt(sum((v - mean) ** 2 for v in self.values) / n)
        return {"mean": mean, "min": min(self.values), "max": max(self.values), "std": std}


def tolerance(
    problem: Problem, q: Quantity, tol: float | Mapping[str, float] = 0.05, runs: int = 500, seed: int = 0
) -> Spread:
    """Each part with a value given, varied within its tolerance (``tol``: every resistor, capacitor and
    inductor alike; by kind prefix, ``{"C": 0.1}``) — solved once with them as letters, then each build."""
    of = {
        k: (tol.get(k.kind.prefix, 0.0) if isinstance(tol, Mapping) else tol)
        for k in problem.given
        if isinstance(k, Element) and k.kind.positive
    }
    varied = {k: float(cast(sp.Expr, problem.given[k])) for k, t in of.items() if t}
    letters = {k: sp.Symbol(f"tol_{i}") for i, k in enumerate(varied)}
    h = solve(Problem(problem.circuit, {**problem.given, **letters}), None)(q)
    at = sp.lambdify(list(letters.values()), h, "math")
    rng = random.Random(seed)
    values = tuple(float(at(*(v * (1 + rng.uniform(-of[k], of[k])) for k, v in varied.items()))) for _ in range(runs))
    return Spread(values)
