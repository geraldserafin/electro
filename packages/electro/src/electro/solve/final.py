"""A frame of a closed circuit, solved. Solving is parsing: what is left (``Laws``) is the input, a step takes
one equation and gives one unknown, and the ways are a list (``algebra``'s combinators):

- ``ways``: every combination of the ways of the elements of several (``sequence``: the textbook's diode on,
  or off), each assumed;
- ``many (alone one_root)``: one unknown at a time, from an equation with it alone left — the log the steps;
- ``together``: what is left, at once;
- ``hold``: what each assumed way needs holds, and every equation left with nothing in it.

No way left is a contradiction; several, more than one answer; one with unknowns left, missing data.
Beyond algebra (an ``exp``) Newton finds the frame, its sources raised from nothing. The final frame is the
one the circuit comes to: one frame infinitely long (DC), or, with sines of one frequency, turning at it
(AC)."""

from __future__ import annotations

import graphlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import ClassVar

import sympy as sp

from ..circuit.algebra import (
    Known,
    Laws,
    Origin,
    SolutionStep,
    Solve,
    Way,
    alone,
    expr,
    failed,
    many,
    rejected,
    symbols_in,
    then,
)
from ..circuit.element import Element
from ..circuit.names import Names
from ..circuit.quantities import Current, Power, Quantity, Scaled, Voltage
from ..circuit.time import TIME
from ..errors import Ambiguous, Contradiction, MissingData, NotLinear, Undetermined
from ..frame.formula import Closed, Formula, close, conditions, formula, parameter_values, scaled
from ..frame.reading import AC, DC, Step, before, frequencies
from ..numeric.code import compile_equations
from ..numeric.engine import homotopy

SOURCES = sp.Symbol("λ")
"""How far every independent source is raised: 0 is all off, 1 as given (Newton's way up)."""


@dataclass(frozen=True)
class Solution:
    """One frame of a circuit: what was found of its named variables (``values``), what is left not found
    (``unknowns``), what was given (``given``, as it was), the steps, the frame and when it ends (``time``; ∞:
    all settled)."""

    circuit: Element
    values: Mapping[sp.Symbol, sp.Expr]
    unknowns: frozenset[sp.Symbol]
    names: Names
    data: Mapping[sp.Symbol, sp.Expr] = field(default_factory=dict)
    given: Mapping = field(default_factory=dict)
    steps: tuple[SolutionStep, ...] = ()
    frame: Step = field(default_factory=DC)
    time: sp.Expr = sp.oo

    by_name: ClassVar[Callable[[str, Solution], sp.Expr] | None] = None
    """How a quantity written as text (``"U_R_1 / I_R_1"``) is read, when something reads it (the notebook)."""

    def __call__(self, q: Quantity | Scaled | str) -> sp.Expr:
        """``q``'s value (by name too, when ``by_name`` reads names). What the data do not pin down:
        ``MissingData``."""
        if isinstance(q, str) and Solution.by_name is not None:
            return Solution.by_name(q, self)
        return self.answers(q)[q]

    def answers(self, *qs: Quantity | Scaled) -> dict:
        """Each of ``qs`` found; or ``MissingData``: how many data more all of them need (``lacking``: what of
        them is still not pinned down), and those found."""
        found, lacking, targets = {}, [], []
        for q in qs:
            value = sp.simplify(self.of(q))
            if value.free_symbols & self.unknowns:
                lacking.append(value)
                targets.append(q)
            else:
                found[q] = value
        if not lacking:
            return found
        free = {x for e in lacking for x in e.free_symbols} & self.unknowns
        err = MissingData(len(free), found, [q for q in targets if isinstance(q, Quantity)])
        err.circuit, err.solution, err.lacking = self.circuit, self, tuple(lacking)
        raise err

    def of(self, q: Quantity | Scaled) -> sp.Expr:
        """``q`` with what was found in: a value, or an expression of what was not."""
        if isinstance(q, Power):
            return self.frame.product(self.of(Voltage(q.of)), self.of(Current(q.of)))
        return self.evaluated(self.names.of(q))

    def evaluated(self, e: sp.Expr) -> sp.Expr:
        """``e``, of the circuit's named variables, with what was found and what was given in."""
        return e.xreplace(dict(self.values)).xreplace(dict(self.data))


def final(circuit: Element, values: Mapping, frame: Step | None = None) -> Solution:
    """Where the circuit comes to, ``values`` in: by default one frame infinitely long; with sines in time
    of one frequency, turning at it."""
    return frame_after(circuit, values, frame or settled(circuit, values))


def settled(circuit: Element, values: Mapping) -> Step:
    """How the circuit settles: with sines in time of one frequency, turning at it (``AC``); else DC."""
    c = close(circuit)
    found = {
        w
        for e in c.laws.map(lambda e: e.xreplace(parameter_values(circuit, values, c.names))).expressions()
        for w in frequencies(e)
    }
    return AC(found.pop()) if len(found) == 1 else DC()


def frame_after(circuit: Element, values: Mapping, frame: Step, before: Solution | None = None) -> Solution:
    """One frame of ``circuit``, ``frame`` long, after ``before`` (by default from rest)."""
    try:
        return _frame(close(circuit), values, frame, before)
    except Undetermined as err:
        err.circuit, err.values, err.frame = circuit, values, frame
        raise


def _frame(c: Closed, values: Mapping, frame: Step, after: Solution | None) -> Solution:
    time = (after.time if after is not None else sp.Integer(0)) + frame.dt if frame.dt not in (0, sp.oo) else sp.oo
    under_d, under_pre = c.remembered
    given = parameter_values(c.circuit, values, c.names)
    given |= {before(x): after.evaluated(x) if after is not None else sp.Integer(0) for x in under_d | under_pre}
    given |= {TIME: time} if time != sp.oo else {}
    left = formula(c, frame, given, tuple(conditions(values, c.names)))
    if any(e.has(TIME) for e in left.laws.expressions()):
        raise Undetermined("its data change in time: simulate it")
    if _is_algebraic(left):
        found, steps = solved(left)
    elif frame.dt == 0:
        raise NotLinear("a non-linear circuit in frames infinitely short: around its working point (not yet)")
    else:
        left = formula(c, frame, scaled(given, c.circuit, c.names, SOURCES))
        found, steps = _by_newton(left)
    unknown = frozenset(left.unknowns) - set(found)
    every = left.laws.complete(found)
    unknown |= {x for x, v in every.items() if symbols_in(v) & unknown}
    shown = _shown(left, every, unknown)
    checks = len(steps) - next((k for k, st in enumerate(reversed(steps)) if st.how != "checked"), len(steps))
    steps = (*steps[:checks], *shown, *steps[checks:])
    return Solution(c.circuit, every, unknown, left.names, left.given, dict(values), steps, frame, time)


def solved(left: Formula) -> tuple[Known, tuple[SolutionStep, ...]]:
    """The one way the frame goes, as by hand: what it found and the steps (the tries before it too)."""
    outcomes = by_hand(left)(Laws(left.laws.equations, left.laws.choices))
    fitting = [o for o in outcomes if not failed(o)]
    if not fitting:
        raise (
            Undetermined("no way of its elements fits")
            if left.laws.choices
            else Contradiction("no solution: the data contradict each other")
        )
    if len(fitting) > 1:
        if left.laws.choices:
            raise Undetermined("more than one way fits")
        raise Ambiguous([{x: v for x, v in o.found().items() if x in left.params} for o in fitting])
    first = outcomes.index(fitting[0])
    tries = tuple(s for o in outcomes[:first] for s in o.log)
    return fitting[0].found(), (*tries, *fitting[0].log)


def by_hand(left: Formula) -> Solve:
    unknowns = set(left.unknowns)

    def one_root(e: sp.Expr, x: sp.Symbol) -> list[sp.Expr] | None:
        if symbols_in(e) & unknowns != {x}:
            return None
        return [sp.simplify(r) for r in sp.solve(e, x) if _fits(x, r, left)]

    return then(ways, many(alone(unknowns, one_root)), together(left), hold(unknowns))


def ways(laws: Laws) -> list[Laws]:
    """Every combination of the elements' ways, each assumed: its equations hold now, and it stays the one
    way of its element, what it needs to be checked."""
    out = [Laws(laws.equations, (), laws.log)]
    for choice in laws.choices:
        out = [_assumed(k, w) for k in out for w in choice]
    return out


def _assumed(laws: Laws, way: Way) -> Laws:
    step = SolutionStep((), (), (Origin("assumed", way.element, case=way.name),), "assumed")
    return Laws((*laws.equations, *way.equations), (*laws.choices, (way,)), (*laws.log, step))


def together(left: Formula) -> Solve:
    """What is left, at once: one way for each solution."""

    def solve(laws: Laws) -> list[Laws]:
        rest = [q for q in laws.equations if symbols_in(q.expr) & set(left.unknowns)]
        if not rest:
            return [laws]
        exprs = [q.expr for q in rest]
        xs = sorted({x for e in exprs for x in symbols_in(e)} & set(left.unknowns), key=str)
        options = [f for f in sp.solve(exprs, xs, dict=True) if all(_fits(x, v, left) for x, v in f.items())]
        if not options:
            return [rejected(laws, rest[0].origin)]
        step = lambda f: SolutionStep(
            tuple(f), tuple(f.values()), tuple(q.origin for q in rest), "together", tuple(exprs)
        )  # noqa: E731
        return [laws.put(f, step(f)) for f in ({x: sp.simplify(v) for x, v in o.items()} for o in options)]

    return solve


def hold(unknowns: set[sp.Symbol]) -> Solve:
    """Every equation left with no unknown in it holds, and what each assumed way needs (≥ 0)."""

    def check(laws: Laws) -> list[Laws]:
        for q in laws.equations:
            if not symbols_in(q.expr) & unknowns and sp.simplify(q.expr) != 0:
                return [rejected(laws, q.origin)]
        checked = []
        for (way,) in laws.choices:
            needs = [sp.simplify(h) for h in way.holds]
            if any(symbols_in(v) & unknowns for v in needs):
                return [rejected(laws, Origin("holds", way.element, case=way.name))]
            if any(not v.is_number for v in needs):
                raise Undetermined("which way each element is depends on values not given")
            if any(float(v) < -1e-12 for v in needs):
                return [rejected(laws, Origin("holds", way.element, case=way.name))]
            checked.append(SolutionStep((), (), (Origin("holds", way.element, case=way.name),), "checked"))
        return [Laws(laws.equations, laws.choices, (*laws.log, *checked))]

    return check


def _fits(x: sp.Symbol, value: object, left: Formula) -> bool:
    """Not a negative value of what is never negative: a resistance of −34 Ω is no circuit."""
    v = expr(value)
    return x not in left.positive or not (v.is_number and v.is_real and float(v) < 0)


def _is_algebraic(left: Formula) -> bool:
    """Polynomial in its unknowns, over a common denominator (an unknown resistance times a current too)."""
    try:
        for q in left.laws.equations:
            sp.Poly(sp.numer(sp.together(q.expr)), *left.unknowns) if left.unknowns else None
        return True
    except sp.PolynomialError:
        return False


def _by_newton(left: Formula):
    """Every value is needed; the sources are raised from nothing."""
    exprs = [q.expr for q in left.laws.equations]
    unknowns = list(left.unknowns)
    if any(x not in {*unknowns, SOURCES} for e in exprs for x in symbols_in(e)):
        raise Undetermined("a non-linear circuit is solved with every value given")
    currents = [v for s in left.laws.log for v in s.values]
    numeric = compile_equations(exprs, unknowns, [SOURCES], unknowns, limited=False, currents=currents)
    found = homotopy(lambda x0, lam: numeric.newton(x0, [lam]), len(numeric.unknowns))
    if found is None:
        raise Undetermined("Newton did not get there")
    values = {u: sp.Float(v) for u, v in zip(numeric.unknowns, found) if u in unknowns}
    origins = tuple(q.origin for q in left.laws.equations)
    return values, (SolutionStep(tuple(values), tuple(values.values()), origins, "numerically"),)


def _shown(left: Formula, every: Known, unknown) -> tuple[SolutionStep, ...]:
    """Each quantity that went on the way and that a book names (an element's current, a point's potential —
    not a terminal's, not what a wire made one), its value now known; each after those its equation holds
    (a topological order)."""
    points = set(left.names.points.values())
    named = {}
    for s in left.laws.log:
        (x,) = s.found
        terminal = x.name.startswith("V_") and x not in points
        value = every.get(x)
        if isinstance(x, sp.Dummy) or s.because[0].what == "wire" or terminal or x in named:
            continue
        if value is not None and not symbols_in(value) & unknown:
            named[x] = SolutionStep((x,), (value,), s.because, equations=s.equations)
    after = {x: symbols_in(s.equations[0]) & set(named) - {x} for x, s in named.items()}
    return tuple(named[x] for x in graphlib.TopologicalSorter(after).static_order())
