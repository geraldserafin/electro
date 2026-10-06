"""A frame of a closed circuit, its values in: its formula (``formula``) solved — by hand, one unknown at a
time from an equation that gives it alone (``Laws.eliminate`` again, its log the steps), the rest together;
elements of several ways by cases (each combination of their ways, as the list monad's ``sequence``, assumed
and checked); beyond algebra (an ``exp``) by Newton — and every quantity back through the log. The final frame is the one the circuit comes to: one frame infinitely long
(DC), or, with sines of one frequency, turning at it (AC)."""

from __future__ import annotations

import itertools
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import ClassVar

import sympy as sp

from ..circuit.algebra import Equation, Known, Laws, Origin, SolutionStep, Way, expr, subs, symbols_in
from ..circuit.element import Element
from ..circuit.quantities import Current, Power, Quantity, Scaled, Voltage
from ..circuit.time import TIME
from ..errors import Ambiguous, Contradiction, MissingData, NotLinear, Undetermined
from ..frame.formula import Formula, Names, formula
from ..frame.reading import AC, DC, Step, frequencies
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
    found = {w for e in formula(circuit, values, DC()).laws.expressions() for w in frequencies(e)}
    return AC(found.pop()) if len(found) == 1 else DC()


def frame_after(circuit: Element, values: Mapping, frame: Step, before: Solution | None = None) -> Solution:
    """One frame of ``circuit``, ``frame`` long, after ``before`` (by default from rest)."""
    try:
        return _frame(circuit, values, frame, before)
    except Undetermined as err:
        err.circuit, err.values, err.frame = circuit, values, frame
        raise


def _frame(circuit: Element, values: Mapping, frame: Step, before: Solution | None) -> Solution:
    left = formula(circuit, values, frame, before)
    if any(e.has(TIME) for e in left.laws.expressions()):
        raise Undetermined("its data change in time: simulate it")
    if left.laws.choices:
        found, steps = _by_cases(left)
    elif _is_algebraic(left):
        found, steps = by_hand(left, left.laws)
    elif frame.dt == 0:
        raise NotLinear("a non-linear circuit in frames infinitely short: around its working point (not yet)")
    else:
        left = formula(circuit, values, frame, before, sources=SOURCES)
        found, steps = _by_newton(left)
    unknown = frozenset(left.unknowns) - set(found)
    every = left.laws.complete(found)
    unknown |= {x for x, v in every.items() if symbols_in(v) & unknown}
    traced = _traced(steps, left, every, unknown)
    return Solution(circuit, every, unknown, left.names, left.values, dict(values), traced, frame, left.time)


def by_hand(left: Formula, laws: Laws) -> tuple[Known, tuple[SolutionStep, ...]]:
    """One unknown at a time, from an equation with it alone left (one value for it: a resistance from its
    power has two, and waits for the rest); the rest together. An equation with none left must hold, or the
    data contradict each other."""
    unknowns = set(left.unknowns)

    def alone(e: sp.Expr, x: sp.Symbol) -> sp.Expr | None:
        if symbols_in(e) & unknowns != {x}:
            return None
        roots = [r for r in sp.solve(e, x) if _fits(x, r, left)]
        if not roots:
            raise Contradiction("no solution: the data contradict each other")
        return sp.simplify(roots[0]) if len(roots) == 1 else None

    done = Laws(laws.equations).eliminate(unknowns, alone)
    found = {x: v for s in done.log for x, v in zip(s.found, s.values)}
    rest = [q for q in done.equations if symbols_in(q.expr) & unknowns]
    if any(sp.simplify(q.expr) != 0 for q in done.equations if q not in rest):
        raise Contradiction("no solution: the data contradict each other")
    if not rest:
        return found, done.log
    exprs = [q.expr for q in rest]
    xs = sorted({x for e in exprs for x in symbols_in(e)} & unknowns, key=str)
    options = [f for f in sp.solve(exprs, xs, dict=True) if all(_fits(x, v, left) for x, v in f.items())]
    if not options:
        raise Contradiction("no solution: the data contradict each other")
    if len(options) > 1:
        raise Ambiguous([{x: sp.simplify(v) for x, v in f.items() if x in left.params} for f in options])
    together = {x: sp.simplify(v) for x, v in options[0].items()}
    origins = tuple(q.origin for q in rest)
    step = SolutionStep(tuple(together), tuple(together.values()), origins, "together", tuple(exprs))
    return {**found, **together}, (*done.log, step)


def _fits(x: sp.Symbol, value: object, left: Formula) -> bool:
    """Not a negative value of what is never negative: a resistance of −34 Ω is no circuit."""
    v = expr(value)
    return x not in left.positive or not (v.is_number and v.is_real and float(v) < 0)


def _is_algebraic(left: Formula) -> bool:
    """Polynomial in its unknowns, over a common denominator (an unknown resistance times a current too)."""
    if not left.unknowns:
        return True
    try:
        for q in left.laws.equations:
            sp.Poly(sp.numer(sp.together(q.expr)), *left.unknowns)
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


def _by_cases(left: Formula):
    """Elements of several ways (a textbook diode), solved as by hand: assume a way for each, solve, check that
    what each way needs holds; if it does not, the next assumption. The tries are the steps."""
    tried: list[SolutionStep] = []
    fitting = []
    for combination in itertools.product(*left.laws.choices):
        assumed = [_said("assumed", w) for w in combination]
        assuming = Laws(left.laws.equations + tuple(q for w in combination for q in w.equations))
        try:
            values, steps = by_hand(left, assuming)
        except Undetermined:
            tried += [*assumed, _said("rejected", combination[0])]
            continue
        checks = [(w, sp.simplify(subs(h, values))) for w in combination for h in w.holds]
        if any(symbols_in(v) & set(left.unknowns) for _, v in checks):
            continue
        if any(not v.is_number for _, v in checks):
            raise Undetermined("which way each element is depends on values not given")
        broken = next((w for w, v in checks if float(v) < -1e-12), None)
        if broken is not None:
            tried += [*assumed, *steps, _said("rejected", broken)]
            continue
        fitting.append((values, (*tried, *assumed, *steps, *(_said("checked", w) for w in combination))))
    if not fitting:
        raise Undetermined("no way of its elements fits")
    if len(fitting) > 1:
        raise Undetermined("more than one way fits")
    return fitting[0]


def _said(how: str, way: Way) -> SolutionStep:
    what = "assumed" if how == "assumed" else "holds"
    return SolutionStep((), (), (Origin(what, way.element, case=way.name),), how)


def _traced(found: Sequence[SolutionStep], left: Formula, values: Known, unknown) -> tuple[SolutionStep, ...]:
    """The steps as the solving left them: what was found of what was left, then each quantity that went on
    the way a book names (an element's current, a point's potential — never a joining one), its value now
    known, each once all it is worked out from is."""
    shown: set[sp.Symbol] = set()
    waiting = []
    points = set(left.names.points.values())
    for s in left.laws.log:
        (x,), q = s.found, Equation(s.equations[0], s.because[0])
        value = values.get(x)
        terminal = x.name.startswith("V_") and x not in points
        named = not isinstance(x, sp.Dummy) and q.origin.what != "wire" and not terminal
        if named and x not in shown and value is not None and not symbols_in(value) & unknown:
            shown.add(x)
            waiting.append((x, value, q))
    known = {x for step in found for x in step.found}
    eliminated = []
    while waiting:
        ready = next(
            (w for w in waiting if not {y for y in symbols_in(w[2].expr) - {w[0]} if y in shown} - known), waiting[0]
        )
        waiting.remove(ready)
        x, value, q = ready
        known.add(x)
        eliminated.append(SolutionStep((x,), (value,), (q.origin,), equations=(q.expr,)))
    checks = next((k for k, st in enumerate(reversed(found)) if st.how != "checked"), len(found))
    return (*found[: len(found) - checks], *eliminated, *found[len(found) - checks :])
