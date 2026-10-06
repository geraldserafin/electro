"""A frame of a closed circuit, its values in: its formula (``formula``) solved — linear by algebra, step by
step; elements of several ways by cases; beyond algebra (an ``exp``) by Newton — and every quantity back
through what joining eliminated. The final frame is the one the circuit comes to: one frame infinitely long
(DC), or, with sines of one frequency, turning at it (AC)."""

from __future__ import annotations

import itertools
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace

import sympy as sp

from .algebra import Origin, SolutionStep, Way, subs, symbols_in
from .by_hand import Known, solve_by_hand
from .code import compile_equations
from .element import Element
from .engine import homotopy
from .errors import Contradiction, MissingData, NotLinear, Undetermined
from .formula import Formula, Names, System, formula
from .frame import AC, DC, Step, frequencies
from .quantities import Current, Parameter, Power, Quantity, Scaled, Voltage
from .time import TIME

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

    def __call__(self, q: Quantity | Scaled | str) -> sp.Expr:
        """``q``'s value; or by name, ``"I_R_1"``, an expression of names too (``"U_E_1 / I_E_1"``). What the
        data do not pin down: ``MissingData`` — how many data more, and which would do."""
        if isinstance(q, str):
            from .names import evaluated

            return evaluated(q, self)
        if isinstance(q, Power):
            return sp.simplify(self.frame.product(self(Voltage(q.of)), self(Current(q.of))))
        value = sp.simplify(self.evaluated(self.names.of(q)))
        free = sorted(value.free_symbols & self.unknowns, key=str)
        if free:
            options = self._pinning(free[0], value) if len(free) == 1 else []
            err = MissingData(len(free), options, {}, [q] if isinstance(q, Quantity) else [])
            err.circuit = self.circuit
            raise err
        return value

    def answers(self, *qs: Quantity | Scaled) -> dict:
        """Each of ``qs`` found; or ``MissingData``: how many data more all of them need, which one would do (when
        one is), and those found."""
        found, lacking, targets = {}, [], []
        for q in qs:
            value = sp.simplify(self.evaluated(self.names.of(q)))
            if value.free_symbols & self.unknowns:
                lacking.append(value)
                targets.append(q)
            else:
                found[q] = value
        if not lacking:
            return found
        free = sorted({x for e in lacking for x in e.free_symbols} & self.unknowns, key=str)
        options = self._pinning(free[0], sp.Add(*lacking)) if len(free) == 1 else []
        err = MissingData(len(free), options, found, targets)
        err.circuit = self.circuit
        raise err

    def evaluated(self, e: sp.Expr) -> sp.Expr:
        """``e``, of the circuit's named variables, with what was found and what was given in."""
        return e.xreplace(dict(self.values)).xreplace(dict(self.data))

    def _pinning(self, x: sp.Symbol, lacking: sp.Expr) -> list[Quantity]:
        """Quantities each of which, given, would pin ``x`` and with it what is lacking."""
        out = []
        for q in self._measurable():
            e = self.evaluated(self.names.of(q))
            if x not in e.free_symbols:
                continue
            roots = sp.solve(e - sp.Dummy("k"), x)
            if len(roots) == 1 and not symbols_in(subs(lacking, {x: roots[0]})) & self.unknowns:
                out.append(q)
        return out

    def _measurable(self) -> list[Quantity]:
        """Each element's parameters, and of a two-terminal one its voltage and current."""
        out: list[Quantity] = []
        for e in self.circuit.members:
            if len(e.terminals) == 2:
                out += [Voltage(e), Current(e)]
            out += [Parameter(e, w) for w in e.parameters]
        return out


def final(circuit: Element, values: Mapping, frame: Step | None = None) -> Solution:
    """Where the circuit comes to, ``values`` in: by default one frame infinitely long; with sines in time
    of one frequency, turning at it."""
    return frame_after(circuit, values, frame or settled(circuit, values))


def settled(circuit: Element, values: Mapping) -> Step:
    """How the circuit settles: with sines in time of one frequency, turning at it (``AC``); else DC."""
    left = formula(circuit, values, DC())
    said = [*(q.expr for q in left.system.equations), *(v for _, v, _ in left.definitions)]
    found = {w for e in said for w in frequencies(e)}
    return AC(found.pop()) if len(found) == 1 else DC()


def frame_after(circuit: Element, values: Mapping, frame: Step, before: Solution | None = None) -> Solution:
    """One frame of ``circuit``, ``frame`` long, after ``before`` (by default from rest)."""
    try:
        return _frame(circuit, values, frame, before)
    except Undetermined as err:
        err.circuit = circuit
        raise


def _frame(circuit: Element, values: Mapping, frame: Step, before: Solution | None) -> Solution:
    left = formula(circuit, values, frame, before)
    system = left.system
    if any(q.expr.has(TIME) for q in system.equations) or any(v.has(TIME) for _, v, _ in left.definitions):
        raise Undetermined("its data change in time: simulate it")
    if system.choices:
        found, unknown, steps = _by_cases(system)
    elif _is_algebraic(system):
        found, unknown, steps = _by_algebra(circuit, values, frame, system)
    elif frame.dt == 0:
        raise NotLinear("a non-linear circuit in frames infinitely short: around its working point (not yet)")
    else:
        left = formula(circuit, values, frame, before, sources=SOURCES)
        found, unknown, steps = _by_newton(left)
    every = left.complete(found)
    unknown = frozenset(unknown | {x for x, v in every.items() if symbols_in(v) & unknown})
    traced = _traced(steps, left, every, unknown)
    return Solution(circuit, every, unknown, left.names, left.values, dict(values), traced, frame, left.time)


def _is_algebraic(system: System) -> bool:
    """Polynomial in its unknowns, over a common denominator (an unknown resistance times a current too)."""
    if not system.unknowns:
        return True
    try:
        for q in system.equations:
            sp.Poly(sp.numer(sp.together(q.expr)), *system.unknowns)
        return True
    except sp.PolynomialError:
        return False


def _by_algebra(circuit: Element, values: Mapping, frame: Step, system: System):
    try:
        found, steps = solve_by_hand(system)
    except Contradiction as err:
        raise Contradiction(str(err), {k: values[k] for k in _clashing(circuit, values, frame)}) from None
    return found, frozenset(system.unknowns) - set(found), steps


def _clashing(circuit: Element, values: Mapping, frame: Step) -> list:
    """The data that clash: those without which it fits."""
    out = []
    for key in values:
        rest = {k: v for k, v in values.items() if k is not key}
        try:
            solve_by_hand(formula(circuit, rest, frame).system)
        except Undetermined:
            continue
        out.append(key)
    return out


def _by_newton(left: Formula):
    """Every value is needed; the sources are raised from nothing."""
    system = left.system
    exprs = [q.expr for q in system.equations]
    unknowns = list(system.unknowns)
    if any(x not in {*unknowns, SOURCES} for e in exprs for x in symbols_in(e)):
        raise Undetermined("a non-linear circuit is solved with every value given")
    currents = [v for _, v, _ in left.definitions]
    numeric = compile_equations(exprs, unknowns, [SOURCES], unknowns, limited=False, currents=currents)
    found = homotopy(lambda x0, lam: numeric.newton(x0, [lam]), len(numeric.unknowns))
    if found is None:
        raise Undetermined("Newton did not get there")
    values = {u: sp.Float(v) for u, v in zip(numeric.unknowns, found) if u in unknowns}
    step = SolutionStep(tuple(values), tuple(values.values()), tuple(q.origin for q in system.equations), "numerically")
    return values, frozenset(), (step,)


def _by_cases(system: System):
    """Elements of several ways (a textbook diode), solved as by hand: assume a way for each, solve, check that
    what each way needs holds; if it does not, the next assumption. The tries are the steps."""
    tried: list[SolutionStep] = []
    fitting = []
    for combination in itertools.product(*system.choices):
        assumed = [_said("assumed", w) for w in combination]
        assuming = replace(
            system, equations=system.equations + tuple(q for w in combination for q in w.equations), choices=()
        )
        try:
            values, steps = solve_by_hand(assuming)
        except Undetermined:
            tried += [*assumed, _said("rejected", combination[0])]
            continue
        checks = [(w, sp.simplify(subs(h, values))) for w in combination for h in w.holds]
        if any(symbols_in(v) & set(system.unknowns) for _, v in checks):
            continue
        if any(not v.is_number for _, v in checks):
            raise Undetermined("which way each element is depends on values not given")
        broken = next((w for w, v in checks if float(v) < -1e-12), None)
        if broken is not None:
            tried += [*assumed, *steps, _said("rejected", broken)]
            continue
        checked = [_said("checked", w) for w in combination]
        fitting.append((values, frozenset(system.unknowns) - set(values), (*tried, *assumed, *steps, *checked)))
    if not fitting:
        raise Undetermined("no way of its elements fits")
    if len(fitting) > 1:
        raise Undetermined("more than one way fits")
    return fitting[0]


def _said(how: str, way: Way) -> SolutionStep:
    what = "assumed" if how == "assumed" else "holds"
    return SolutionStep((), (), (Origin(what, way.element, case=way.name),), how)


def _traced(found: Sequence[SolutionStep], left: Formula, values: Known, unknown) -> tuple[SolutionStep, ...]:
    """The steps as the solving left them: what was found of what was left, then each eliminated quantity a
    book names (an element's current, a point's potential — never a joining one), its value now known, each
    once all it is worked out from is."""
    shown: set[sp.Symbol] = set()
    waiting = []
    points = set(left.names.points.values())
    for x, _, q in left.definitions:
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
