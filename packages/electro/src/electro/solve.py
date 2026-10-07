"""One frame of a circuit, worked out exactly: its laws read in the frame (``frame``), its values in, then its
equations block by block in the order their structure gives (``structure``) — one equation giving one unknown
alone, a block of several together, one beyond algebra (an ``exp``) by Newton. Each block found is a step,
and the steps are what a book shows: the frame's trace, nothing else.

A block may give several values (a resistance from its power): each is a way the frame may go, and those that
later equations rule out are dropped. An element of several ways (the textbook's diode) is each of its ways in
turn, kept where what it needs holds. No way left: the data clash; more than one: the data do not pick one;
unknowns no equation is left for: data missing.

The final frame is the one the circuit comes to: one frame infinitely long (DC), or, with sines of one
frequency, turning at it (AC)."""

from __future__ import annotations

import itertools
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import ClassVar

import sympy as sp

from .circuit import Circuit, Laws, _laws, points
from .element import Equation, Origin, SolutionStep, Way
from .errors import Ambiguous, Contradiction, MissingData, NotLinear, Undetermined
from .frame import AC, DC, Step, before, frequencies, is_before
from .numeric.code import compile_equations
from .numeric.engine import homotopy
from .quantities import Current, Power, Quantity, Scaled, Voltage
from .structure import structure
from .time import TIME, D, Pre
from .values import data, given

Known = dict[sp.Symbol, sp.Expr]


@dataclass(frozen=True)
class Solution:
    """One frame of a circuit: what it found (``values``), what no equation was left for (``unknowns``), the
    parameters' values (``data``) and the values as given (``given``), its steps, the frame and when it ends
    (``time``; ∞: all settled). ``at``: each element's terminal potential as its point's."""

    circuit: Circuit
    values: Known
    unknowns: frozenset[sp.Symbol]
    at: Mapping[sp.Symbol, sp.Expr]
    data: Known = field(default_factory=dict)
    given: Mapping = field(default_factory=dict)
    steps: tuple[SolutionStep, ...] = ()
    frame: Step = field(default_factory=DC)
    time: sp.Expr = sp.oo

    by_name: ClassVar[Callable[[str, Solution], sp.Expr] | None] = None
    """How a quantity written as text (``"U_R_1 / I_R_1"``) is read, when something reads it (the notebook)."""

    def __call__(self, q: Quantity | Scaled | str) -> sp.Expr:
        """``q``'s value. What the data do not pin down: ``MissingData``."""
        if isinstance(q, str) and Solution.by_name is not None:
            return Solution.by_name(q, self)
        return self.answers(q)[q]

    def answers(self, *qs: Quantity | Scaled) -> dict:
        """Each of ``qs`` found; or ``MissingData``: how many data more all of them need, and those found."""
        values = {q: sp.simplify(self.of(q)) for q in qs}
        lacking = {q: v for q, v in values.items() if v.free_symbols & self.unknowns}
        if lacking:
            needed = {x for v in lacking.values() for x in v.free_symbols} & self.unknowns
            err = MissingData(len(needed), {q: v for q, v in values.items() if q not in lacking}, list(lacking))
            err.circuit, err.solution, err.lacking = self.circuit, self, tuple(lacking.values())
            raise err
        return values

    def of(self, q: Quantity | Scaled) -> sp.Expr:
        """``q`` with what was found in: a value, or an expression of what was not."""
        if isinstance(q, Power):
            return self.frame.product(self.of(Voltage(q.of)), self.of(Current(q.of)))
        return self.evaluated(q.expr)

    def evaluated(self, e: sp.Expr) -> sp.Expr:
        """``e``, of the circuit's variables, with what was found and what was given in."""
        return e.xreplace(dict(self.at)).xreplace(self.values).xreplace(self.data)


def final(circuit: Circuit, values: Mapping, frame: Step | None = None) -> Solution:
    """Where the circuit comes to, ``values`` in: by default one frame infinitely long; with sines in time
    of one frequency, turning at it."""
    return frame_after(circuit, values, frame or settled(circuit, values))


def settled(circuit: Circuit, values: Mapping) -> Step:
    """How the circuit settles: with sines in time of one frequency, turning at it (``AC``); else DC."""
    put = given(circuit, values)
    found = {w for e in circuit.closed().expressions() for w in frequencies(e.xreplace(put))}
    return AC(found.pop()) if len(found) == 1 else DC()


def frame_after(circuit: Circuit, values: Mapping, frame: Step, after: Solution | None = None) -> Solution:
    """One frame of ``circuit``, ``frame`` long, after ``after`` (by default from rest)."""
    try:
        return _frame(circuit, values, frame, after)
    except Undetermined as err:
        err.circuit, err.values, err.frame = circuit, values, frame
        raise


def _frame(circuit: Circuit, values: Mapping, frame: Step, after: Solution | None) -> Solution:
    laws = circuit.closed()
    known = given(circuit, values)
    memory = {
        before(x): after.evaluated(x) if after is not None else sp.Integer(0)
        for e in laws.expressions()
        for a in e.atoms(D, Pre)
        for x in [a.args[0]]
    }
    time = (after.time if after is not None else sp.Integer(0)) + frame.dt if frame.dt not in (0, sp.oo) else sp.oo
    read = frame.reading({**known, **memory, **({TIME: time} if time != sp.oo else {})})
    laws = laws.map(read)
    said = [*laws.equations, *(Equation(read(q.expr.xreplace(laws.at)), q.origin) for q in data(values))]
    said += references(
        [*(q.expr for q in said), *laws.expressions()],
        {x for p in points(circuit) for x in sp.sympify(p.potential).free_symbols},
    )
    if any(e.has(TIME) for e in [q.expr for q in said] + laws.expressions()):
        raise Undetermined("its data change in time: simulate it")
    letters = {x for v in known.values() for x in sp.sympify(v).free_symbols} | frame.letters()
    unknowns = {x for e in [q.expr for q in said] + laws.expressions() for x in e.free_symbols} - letters
    unknowns = {x for x in unknowns if not is_before(x)}
    positive = {e.P[w] for e in circuit.members for w in e.positive}
    fits = _fits(positive)
    values_, free, steps = _ways(said, laws.ways, unknowns, fits, frame, values)
    return Solution(circuit, values_, frozenset(free), laws.at, known, dict(values), steps, frame, time)


World = tuple[Known, tuple[SolutionStep, ...]]


def _ways(said, ways, unknowns, fits, frame, values) -> tuple[Known, set[sp.Symbol], tuple[SolutionStep, ...]]:
    """The frame for each combination of the elements' ways (``sequence``), kept where what each needs holds;
    the tries before the one that fits are steps too."""
    tries: list[SolutionStep] = []
    fitting = []
    for combination in itertools.product(*ways) if ways else [()]:
        assumed = tuple(_said("assumed", w) for w in combination)
        try:
            worlds, free = _solve(
                [*said, *(q for w in combination for q in w.equations)], unknowns, fits, frame, values
            )
        except Contradiction:
            if not combination:
                raise
            tries += [*assumed, _said("rejected", combination[0])]
            continue
        for found, steps in worlds:
            needs = [(w, sp.simplify(h.xreplace(found))) for w in combination for h in w.holds]
            broken = next((w for w, v in needs if not v.is_number or float(v) < -1e-12), None)
            if broken is not None:
                tries += [*assumed, *steps, _said("rejected", broken)]
                continue
            fitting.append((found, free, (*tries, *assumed, *steps, *(_said("checked", w) for w in combination))))
    if not fitting:
        raise Undetermined("no way of its elements fits")
    if len(fitting) > 1:
        raise Undetermined("more than one way fits")
    return fitting[0]


def _said(how: str, way: Way) -> SolutionStep:
    return SolutionStep((), (), (Origin("assumed" if how == "assumed" else "holds", way.element, case=way.name),), how)


def _solve(said: Sequence[Equation], unknowns: set[sp.Symbol], fits, frame: Step, values: Mapping):
    """``said`` block by block: every way it goes (each what it found and its steps), and the unknowns no
    equation is left for."""
    s = structure([q.expr.free_symbols & unknowns for q in said])
    worlds: list[World] = [({}, ())]
    for places, xs in (s.over, *s.blocks, s.under):
        eqs = [said[i] for i in places]
        worlds = [w for world in worlds for w in _block(eqs, xs, world, fits, frame)]
        if not worlds:
            raise Contradiction("no solution: the data contradict each other", _clash(eqs, values))
    if len(worlds) > 1:
        raise Ambiguous([{x: v for x, v in found.items() if not x.is_Dummy} for found, _ in worlds])
    return worlds, set(s.free)


def _block(eqs: list[Equation], xs: tuple[sp.Symbol, ...], world: World, fits, frame: Step) -> list[World]:
    """One block: every way its unknowns may be, given what was found."""
    found, steps = world
    exprs = [q.expr.xreplace(found) for q in eqs]
    origins = tuple(q.origin for q in eqs)
    if not xs:
        return [world] if all(sp.simplify(e) == 0 for e in exprs) else []
    if any(f.free_symbols & set(xs) for e in exprs for f in e.atoms(sp.Function)):
        if frame.dt == 0:
            raise NotLinear("a non-linear circuit in frames infinitely short: around its working point (not yet)")
        values = _numerically(exprs, xs)
        step = SolutionStep(xs, tuple(values[x] for x in xs), origins, "numerically", tuple(exprs))
        return [({**found, **values}, (*steps, step))]
    options = _algebra(exprs, list(xs))
    how = "alone" if len(xs) == 1 else "together"
    out = []
    for o in options:
        o = {x: sp.simplify(v) for x, v in o.items()}
        if all(fits(x, v) for x, v in o.items()):
            out.append(
                ({**found, **o}, (*steps, SolutionStep(tuple(o), tuple(o.values()), origins, how, tuple(exprs))))
            )
    return out


def _algebra(exprs: list[sp.Expr], xs: list[sp.Symbol]) -> list[Known]:
    """Every solution, by elimination when the block is of degree one in its unknowns; numbers algebra does
    not need to see into (10^0.7, √2) as letters meanwhile."""
    numbers = {a for e in exprs for a in e.atoms(sp.Pow, sp.Function) if a.is_number and not a.is_Rational}
    if numbers:
        hidden = {a: sp.Dummy() for a in numbers}
        back = {d: a for a, d in hidden.items()}
        found = _algebra([e.xreplace(hidden) for e in exprs], xs)
        return [{x: v.xreplace(back) for x, v in o.items()} for o in found]
    try:
        linear = all(sp.Poly(e, *xs).total_degree() <= 1 for e in exprs)
    except sp.PolynomialError:
        linear = False
    if not linear:
        return sp.solve(exprs, xs, dict=True)
    return [{x: v for x, v in zip(xs, found) if v != x} for found in sp.linsolve(exprs, xs)]


def _numerically(exprs: list[sp.Expr], xs: tuple[sp.Symbol, ...]) -> Known:
    """A block beyond algebra, by Newton: from where everything is 0 to the block itself (``λ`` from 0 to 1,
    what it is at zero taken away, less and less)."""
    if any(e.free_symbols - set(xs) for e in exprs):
        raise Undetermined("a non-linear circuit is solved with every value given")
    lam = sp.Dummy("λ")
    zero = dict.fromkeys(xs, 0)
    shifted = [e - (1 - lam) * e.xreplace(zero) for e in exprs]
    code = compile_equations(shifted, list(xs), [lam], limited=False)
    x = homotopy(lambda x0, at: code.newton(x0, [at]), len(code.unknowns))
    if x is None:
        raise Undetermined("Newton did not get there")
    return {u: sp.Float(v) for u, v in zip(code.unknowns, x) if u in xs}


def _fits(positive: set[sp.Symbol]) -> Callable[[sp.Symbol, sp.Expr], bool]:
    """Not a negative value of what is never negative: a resistance of −34 Ω is no circuit."""

    def fits(x: sp.Symbol, v: sp.Expr) -> bool:
        return x not in positive or not (v.is_number and v.is_real and float(v) < 0)

    return fits


def _clash(eqs: Sequence[Equation], values: Mapping) -> list:
    """The data among equations that clash: those given on quantities, and the given elements whose laws are
    among them."""
    keys = [q.origin.subject for q in eqs if q.origin.what == "given"]
    keys += [q.origin.subject for q in eqs if q.origin.what == "law" and q.origin.subject in values]
    return list(dict.fromkeys(keys))


def references(said: Sequence[sp.Expr], potentials: set[sp.Symbol]) -> list[Equation]:
    """Where nothing fixes how high a piece's potentials stand — its laws hold whatever is added to all of
    them — one of them chosen 0."""
    groups: dict[sp.Symbol, sp.Symbol] = {}

    def find(x: sp.Symbol) -> sp.Symbol:
        while groups.setdefault(x, x) != x:
            x = groups[x]
        return x

    for e in said:
        here = sorted(e.free_symbols & potentials, key=str)
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
        touched = [e for e in said if e.free_symbols & set(members)]
        if touched and all(sp.expand(e.xreplace(shift) - e) == 0 for e in touched):
            out.append(Equation(members[0], Origin("reference", members[0])))
    return out


__all__ = ["Laws", "Solution", "final", "frame_after", "settled"]


# A piece's law at its ends


def law(c: Circuit) -> str:
    """A 1 → 1 piece as a book writes it, ``U = I·(R_1 + R_2)``: its law at its ends, all inside it hidden."""
    U, I = sp.symbols("U I")
    if len(c.left) != 1 or len(c.right) != 1:
        return "; ".join(f"{q.expr} = 0" for q in _laws(c, 0.0, c.left + c.right).equations)
    said = _at_ends(c, U, I)
    params = {p for e in c.members for p in e.P.values()}
    for x, by in ((U, I), (I, U)):
        value = _solved(said, params | {by}).get(x)
        if value is not None and value.free_symbols <= params | {by}:
            return f"{x} = {sp.factor(value)}"
    timeless = [q for q in said if not q.expr.has(D, Pre)]
    found = _solved(timeless, params | {U, I})
    return "; ".join(f"{e} = 0" for e in {sp.factor(q.expr.xreplace(found)) for q in said} - {0})


def _at_ends(c: Circuit, U: sp.Symbol, I: sp.Symbol) -> list[Equation]:
    """The piece's laws, and what it is at its ends: ``U`` across them, ``I`` in at the first."""
    (a,), (b,) = c.left, c.right
    into = sp.Add(*(e.I[t] for e, ps in c.parts for t, p in zip(e.drawn, ps) if p == a))
    end = Origin("end", None)
    laws = _laws(c, 0.0, (a, b)).equations
    return [*laws, Equation(U - (a.potential - b.potential), end), Equation(I - into, end)]


def _solved(said: list[Equation], letters: set[sp.Symbol]) -> Known:
    """What ``said`` gives, in ``letters``; nothing when it cannot be worked out so."""
    unknowns = {s for q in said for s in q.expr.free_symbols} - letters
    try:
        worlds, _ = _solve(said, unknowns, lambda x, v: True, DC(), {})
    except (Undetermined, NotLinear):
        return {}
    return worlds[0][0]
