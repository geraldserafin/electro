"""Textbook methods as roads through the same equations — no law of their own (DESIGN.md §12).

Each takes what the engine offers (``solve``, ``port``, ``matches``) and the elements' laws as they are:
whether a method may be used (linear? which elements are independent sources?) is read off the laws, and
the rules of simplifying (series, parallel, sources in series) are found by computing, not written down.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass

import sympy as sp

from .problem import (
    AC,
    DC,
    PORT_I,
    PORT_U,
    Analysis,
    Current,
    Parameter,
    Problem,
    Quantity,
    Voltage,
    interpret,
    matches,
    port,
    solve,
    subs,
    symbols,
)
from .syntax import GND, KINDS, Element, Net, Node, netlist, rebuild

# --------------------------------------------------------------------------------------- what the laws say


class NotLinear(ValueError):
    """The method holds only for a linear circuit; this element's law is not."""


def is_linear(e: Element, analysis: Analysis | None = None) -> bool:
    """Its law of degree one in U and I (a resistor, a source, a capacitor read by any analysis)."""
    law = sp.expand(interpret(sp.sympify(e.kind.law(PORT_U, PORT_I, sp.Symbol("p"))), analysis or DC()))
    try:
        return sp.Poly(law, PORT_U, PORT_I).total_degree() <= 1
    except sp.PolynomialError:  # (exp(U), a diode's: not a polynomial at all)
        return False


def is_source(e: Element) -> bool:
    """An independent source: its law keeps a term with neither U nor I in it (``U + E``, ``I − J``).
    A resistor's parameter multiplies I; a controlled source's term is another element's quantity."""
    law = sp.sympify(e.kind.law(PORT_U, PORT_I, sp.Symbol("p")))
    return sp.simplify(law.subs({PORT_U: 0, PORT_I: 0})) != 0


# --------------------------------------------------------------------------------------- superposition


@dataclass(frozen=True)
class Superposition:
    quantity: Quantity
    parts: tuple[tuple[Element, sp.Expr], ...]  # each source alone (the others' parameters zero): its share
    total: sp.Expr


def superposition(problem: Problem, q: Quantity, analysis: DC | AC | None = None) -> Superposition:
    """``q`` as the sum of what each independent source makes of it alone."""
    elements = [e for e, _, _ in netlist(problem.circuit).parts]
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
    ends = [n for _, a, b in net.parts for n in (a, b)]
    named = dict(net.named)
    asked = {
        p
        for q in problem.find
        for p in (getattr(q, "at", None), getattr(q, "a", None), getattr(q, "b", None))
        if isinstance(p, (Node, Net))
    }
    # candidates: two elements meeting at a point nothing else touches (series), or on the same two (parallel)
    pairs: list[tuple[str, int, int, int, int, int]] = []  # how, i, j, outer a, outer b, the point between
    for i, (e, a, b) in enumerate(net.parts):
        for j, (f, c, d) in enumerate(net.parts):
            if j <= i or e in held or f in held:
                continue
            if {a, b} == {c, d} and a != b:
                pairs.append(("parallel", i, j, a, b, -1))
            for mid in {a, b} & {c, d}:
                if ends.count(mid) == 2 and named.get(mid) not in (GND, *asked) and len({a, b, c, d}) == 3:
                    outer = [n for n in (a, b) if n != mid] + [n for n in (c, d) if n != mid]
                    pairs.append(("series", i, j, outer[0], outer[1], mid))
    for how, i, j, a, b, _ in pairs:
        two = (net.parts[i], net.parts[j])
        relation = port(two, a, b, s.param, analysis)
        if relation is None:
            continue
        for kind in KINDS:  # (first that fits: a resistor before anything else — an impedance in AC)
            value = matches(relation, kind, analysis)
            if value is None:
                continue
            e, f = two[0][0], two[1][0]
            by = kind(_combined(s.labels[i], s.labels[j]))
            parts = [p for k, p in enumerate(net.parts) if k not in (i, j)] + [(by, a, b)]
            known = {s.param(x): v for x, v in problem.values.items() if isinstance(x, Element)}
            known |= {sp.Symbol(x): v for x, v in problem.values.items() if isinstance(x, str)}
            names = {x.name for x, _, _ in parts}
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
