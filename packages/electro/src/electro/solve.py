"""One frame of a circuit, worked out exactly: ``final`` (where it settles) and ``frame_after`` (one step in
time). The frame's equations are solved block by block, in the order their structure gives (``structure``):
one equation giving one unknown, a block of several together, a block with an ``exp`` by Newton. Each block
solved is a step; the steps are what a book shows.

A block may have several solutions (a resistance from its power): each is followed, and those later
equations rule out are dropped. An element of several ways (the textbook's diode) is tried in each of its
ways and kept where what that way needs holds. No solution left: the data clash. More than one: the data do
not decide. Unknowns no equation is left for: data missing."""

from __future__ import annotations

import itertools
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import ClassVar

import sympy as sp

from .circuit import Circuit, Laws, points
from .errors import Ambiguous, Contradiction, MissingData, NotLinear, Undetermined
from .frame import AC, DC, Step, before, frequencies, is_before
from .laws import Equation, Origin, Way
from .numeric.code import compile_equations
from .numeric.engine import homotopy
from .quantities import Current, Power, Quantity, Scaled, Voltage
from .structure import structure
from .time import TIME, D, Pre
from .values import data, given

Known = dict[sp.Symbol, sp.Expr]


@dataclass(frozen=True)
class SolutionStep:
    """One step of a frame: what it found, the values, and the equations it used (their origins are the
    reason). ``how``: ``"alone"``, ``"together"``, ``"numerically"``, ``"assumed"`` (an element taken to be one
    of its ways), ``"checked"`` (what that way needs holds) or ``"rejected"``."""

    found: tuple[sp.Symbol, ...]
    values: tuple[sp.Expr, ...]
    because: tuple[Origin, ...]
    how: str = "alone"
    equations: tuple[sp.Expr, ...] = ()


@dataclass(frozen=True)
class Solution:
    """A frame worked out: what it found (``values``), the unknowns no equation was left for (``unknowns``),
    the parameters' values (``data``), the values as given (``given``), the steps, the frame and when it ends
    (``time``; ∞ when settled). ``at``: each element terminal's potential as its point's."""

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
    """How a quantity written as text (``"U_R_1 / I_R_1"``) is read, when something reads text (the notebook)."""

    def __call__(self, q: Quantity | Scaled | str) -> sp.Expr:
        """``q``'s value; ``MissingData`` when the data do not pin it down."""
        if isinstance(q, str) and Solution.by_name is not None:
            return Solution.by_name(q, self)
        return self.answers(q)[q]

    def answers(self, *qs: Quantity | Scaled) -> dict:
        """The value of each of ``qs``; ``MissingData`` when some are not pinned down."""
        values = {q: sp.simplify(self.of(q)) for q in qs}
        lacking = {q: v for q, v in values.items() if v.free_symbols & self.unknowns}
        if lacking:
            raise self._missing(values, lacking)
        return values

    def of(self, q: Quantity | Scaled) -> sp.Expr:
        """``q`` with what was found put in: a value, or an expression in what was not found."""
        if isinstance(q, Power):
            return self.frame.product(self.of(Voltage(q.of)), self.of(Current(q.of)))
        return self.evaluated(q.expr)

    def evaluated(self, e: sp.Expr) -> sp.Expr:
        """``e`` with what was found and what was given put in."""
        return e.xreplace(dict(self.at)).xreplace(self.values).xreplace(self.data)

    def _missing(self, values: dict, lacking: dict) -> MissingData:
        needed = {x for v in lacking.values() for x in v.free_symbols} & self.unknowns
        found = {q: v for q, v in values.items() if q not in lacking}
        err = MissingData(len(needed), found, list(lacking))
        err.circuit, err.solution, err.lacking = self.circuit, self, tuple(lacking.values())
        return err


def final(circuit: Circuit, values: Mapping, frame: Step | None = None) -> Solution:
    """Where the circuit settles: DC by default; AC when its sources are sines of one frequency."""
    return frame_after(circuit, values, frame or settled(circuit, values))


def settled(circuit: Circuit, values: Mapping) -> Step:
    """``AC`` at the one frequency of the circuit's sines, else ``DC``."""
    known = given(circuit, values)
    found = {w for e in circuit.closed().expressions() for w in frequencies(e.xreplace(known))}
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
    time = _end(frame, after)
    known = {**given(circuit, values), **_memory(laws, after), **({TIME: time} if time != sp.oo else {})}
    laws = laws.map(frame.reading(known))
    said = _equations(laws, values, frame.reading(known), circuit)
    if any(e.has(TIME) for e in [q.expr for q in said] + laws.expressions()):
        raise Undetermined("its data change in time: simulate it")
    problem = Problem.of(circuit, said, laws, known, frame, values)
    found, free, steps = problem.each_way(said, laws.ways)
    return Solution(circuit, found, frozenset(free), laws.at, known, dict(values), steps, frame, time)


def _end(frame: Step, after: Solution | None) -> sp.Expr:
    """When the frame ends: ∞ for one infinitely long or infinitely short."""
    if frame.dt in (0, sp.oo):
        return sp.oo
    return (after.time if after is not None else sp.Integer(0)) + frame.dt


def _memory(laws: Laws, after: Solution | None) -> Known:
    """What was a frame before (``x⁻``), for each quantity under ``D`` or ``Pre``: as ``after`` has it, or 0 at
    rest."""
    remembered = {a.args[0] for e in laws.expressions() for a in e.atoms(D, Pre)}
    return {before(x): after.evaluated(x) if after is not None else sp.Integer(0) for x in remembered}


def _equations(laws: Laws, values: Mapping, read: Callable, circuit: Circuit) -> list[Equation]:
    """The frame's equations: the laws, the data on quantities, and a reference potential where nothing fixes
    how high a piece's potentials stand."""
    said = [*laws.equations, *(q.map(lambda e: read(e.xreplace(laws.at))) for q in data(values))]
    potentials = {x for p in points(circuit) for x in sp.sympify(p.potential).free_symbols}
    return said + references([*(q.expr for q in said), *laws.expressions()], potentials)


World = tuple[Known, tuple[SolutionStep, ...]]
"""One way a frame may go: what it found, and the steps."""


@dataclass(frozen=True)
class Problem:
    """What a frame asks: its ``unknowns``, those never negative (``positive``), the frame, and the values as
    given (to name the data that clash)."""

    unknowns: frozenset[sp.Symbol]
    positive: frozenset[sp.Symbol]
    frame: Step
    values: Mapping

    @staticmethod
    def of(circuit: Circuit, said: list[Equation], laws: Laws, known: Known, frame: Step, values: Mapping) -> Problem:
        letters = {x for v in known.values() for x in sp.sympify(v).free_symbols} | frame.letters()
        appearing = {x for e in [q.expr for q in said] + laws.expressions() for x in e.free_symbols}
        unknowns = {x for x in appearing - letters if not is_before(x)}
        positive = {e.P[w] for e in circuit.members for w in e.positive}
        return Problem(frozenset(unknowns), frozenset(positive), frame, values)

    def each_way(self, said: list[Equation], ways) -> tuple[Known, set[sp.Symbol], tuple[SolutionStep, ...]]:
        """The frame in each combination of its elements' ways, kept where what each way needs holds. The tries
        before the one that fits are steps too."""
        tries: list[SolutionStep] = []
        fitting = []
        for combination in itertools.product(*ways):
            assumed = tuple(_mark("assumed", w) for w in combination)
            try:
                worlds, free = self.solve([*said, *(q for w in combination for q in w.equations)])
            except Contradiction:
                if not combination:
                    raise
                tries += [*assumed, _mark("rejected", combination[0])]
                continue
            for found, steps in worlds:
                broken = _broken(combination, found)
                if broken is not None:
                    tries += [*assumed, *steps, _mark("rejected", broken)]
                else:
                    checked = tuple(_mark("checked", w) for w in combination)
                    fitting.append((found, free, (*tries, *assumed, *steps, *checked)))
        if len(fitting) != 1:
            raise Undetermined("no way of its elements fits" if not fitting else "more than one way fits")
        return fitting[0]

    def solve(self, said: Sequence[Equation]) -> tuple[list[World], set[sp.Symbol]]:
        """``said`` block by block: every way it may go, and the unknowns no equation is left for."""
        s = structure([q.expr.free_symbols & self.unknowns for q in said])
        worlds: list[World] = [({}, ())]
        for places, xs in (s.over, *s.blocks, s.under):
            eqs = [said[i] for i in places]
            worlds = [w for world in worlds for w in self.block(eqs, xs, world)]
            if not worlds:
                raise Contradiction("no solution: the data contradict each other", _clash(eqs, self.values))
        if len(worlds) > 1:
            raise Ambiguous([{x: v for x, v in found.items() if not x.is_Dummy} for found, _ in worlds])
        return worlds, set(s.free)

    def block(self, eqs: list[Equation], xs: tuple[sp.Symbol, ...], world: World) -> list[World]:
        """One block, given what was found: every way its unknowns may be."""
        found, steps = world
        exprs = [q.expr.xreplace(found) for q in eqs]
        origins = tuple(q.origin for q in eqs)
        if not xs:
            return [world] if all(sp.simplify(e) == 0 for e in exprs) else []
        if _beyond_algebra(exprs, xs):
            values = self.numerically(exprs, xs)
            step = SolutionStep(xs, tuple(values[x] for x in xs), origins, "numerically", tuple(exprs))
            return [({**found, **values}, (*steps, step))]
        how = "alone" if len(xs) == 1 else "together"
        options = [{x: sp.simplify(v) for x, v in o.items()} for o in _algebra(exprs, list(xs))]
        return [
            ({**found, **o}, (*steps, SolutionStep(tuple(o), tuple(o.values()), origins, how, tuple(exprs))))
            for o in options
            if all(self.fits(x, v) for x, v in o.items())
        ]

    def numerically(self, exprs: list[sp.Expr], xs: tuple[sp.Symbol, ...]) -> Known:
        if self.frame.dt == 0:
            raise NotLinear("a non-linear circuit in frames infinitely short: around its working point (not yet)")
        return _numerically(exprs, xs)

    def fits(self, x: sp.Symbol, v: sp.Expr) -> bool:
        """Not a negative value of what is never negative: a resistance of −34 Ω is no circuit."""
        return x not in self.positive or not (v.is_number and v.is_real and float(v) < 0)


def _mark(how: str, way: Way) -> SolutionStep:
    """A step about an element's way: assumed, checked or rejected."""
    return SolutionStep((), (), (Origin("assumed" if how == "assumed" else "holds", way.element, case=way.name),), how)


def _broken(combination: tuple[Way, ...], found: Known) -> Way | None:
    """The first assumed way whose needs (each ≥ 0) do not hold."""
    for w in combination:
        needs = [sp.simplify(h.xreplace(found)) for h in w.holds]
        if any(not v.is_number or float(v) < -1e-12 for v in needs):
            return w
    return None


def _beyond_algebra(exprs: list[sp.Expr], xs: tuple[sp.Symbol, ...]) -> bool:
    """An unknown inside a function (an ``exp``, a junction's): Newton's, not algebra's."""
    return any(f.free_symbols & set(xs) for e in exprs for f in e.atoms(sp.Function))


def _algebra(exprs: list[sp.Expr], xs: list[sp.Symbol]) -> list[Known]:
    """Every solution: by linear elimination when the block is linear, else ``sp.solve``. Irrational numbers
    (10^0.7, √2) are hidden behind letters meanwhile, so sympy does not build fields of them."""
    numbers = {a for e in exprs for a in e.atoms(sp.Pow, sp.Function) if a.is_number and not a.is_Rational}
    if numbers:
        hidden = {a: sp.Dummy() for a in numbers}
        back = {d: a for a, d in hidden.items()}
        return [{x: v.xreplace(back) for x, v in o.items()} for o in _algebra([e.xreplace(hidden) for e in exprs], xs)]
    if not _linear(exprs, xs):
        return sp.solve(exprs, xs, dict=True)
    return [{x: v for x, v in zip(xs, found) if v != x} for found in sp.linsolve(exprs, xs)]


def _linear(exprs: list[sp.Expr], xs: list[sp.Symbol]) -> bool:
    try:
        return all(sp.Poly(e, *xs).total_degree() <= 1 for e in exprs)
    except sp.PolynomialError:
        return False


def _numerically(exprs: list[sp.Expr], xs: tuple[sp.Symbol, ...]) -> Known:
    """A block with an ``exp``, by Newton, walked from where everything is 0 to the block itself: at λ the
    block less (1 − λ) times what it is at 0."""
    if any(e.free_symbols - set(xs) for e in exprs):
        raise Undetermined("a non-linear circuit is solved with every value given")
    lam = sp.Dummy("λ")
    at_zero = [e.xreplace(dict.fromkeys(xs, 0)) for e in exprs]
    code = compile_equations([e - (1 - lam) * z for e, z in zip(exprs, at_zero)], list(xs), [lam], limited=False)
    x = homotopy(lambda x0, at: code.newton(x0, [at]), len(code.unknowns))
    if x is None:
        raise Undetermined("Newton did not get there")
    return {u: sp.Float(v) for u, v in zip(code.unknowns, x) if u in xs}


def _clash(eqs: Sequence[Equation], values: Mapping) -> list:
    """The data among equations that clash: data on quantities, and the elements given whose laws are there."""
    keys = [q.origin.subject for q in eqs if q.origin.what == "given"]
    keys += [q.origin.subject for q in eqs if q.origin.what == "law" and q.origin.subject in values]
    return list(dict.fromkeys(keys))


def references(said: Sequence[sp.Expr], potentials: set[sp.Symbol]) -> list[Equation]:
    """For each piece whose potentials nothing fixes (its laws hold whatever is added to all of them), one of its
    potentials set to 0."""
    return [
        Equation(piece[0], Origin("reference", piece[0]))
        for piece in _pieces(said, potentials)
        if _floating(piece, said)
    ]


def _pieces(said: Sequence[sp.Expr], potentials: set[sp.Symbol]) -> list[list[sp.Symbol]]:
    """The potentials, in groups that equations tie together."""
    group: dict[sp.Symbol, sp.Symbol] = {}

    def find(x: sp.Symbol) -> sp.Symbol:
        while group.setdefault(x, x) != x:
            x = group[x]
        return x

    for e in said:
        here = sorted(e.free_symbols & potentials, key=str)
        for a, b in zip(here, here[1:]):
            group[find(a)] = find(b)
    pieces: dict[sp.Symbol, list[sp.Symbol]] = {}
    for x in group:
        pieces.setdefault(find(x), []).append(x)
    return [sorted(p, key=str) for p in pieces.values()]


def _floating(piece: list[sp.Symbol], said: Sequence[sp.Expr]) -> bool:
    """Whether every equation on ``piece`` holds whatever is added to all its potentials."""
    lifted = sp.Dummy("c")
    shift = {x: x + lifted for x in piece}
    touched = [e for e in said if e.free_symbols & set(piece)]
    return bool(touched) and all(sp.expand(e.xreplace(shift) - e) == 0 for e in touched)


# A piece's law at its ends


def law(c: Circuit) -> str:
    """A 1 → 1 piece as a book writes it, ``U = I·(R_1 + R_2)``: its law at its ends, everything inside hidden."""
    U, I = sp.symbols("U I")
    if len(c.left) != 1 or len(c.right) != 1:
        return "; ".join(f"{q.expr} = 0" for q in c.laws_except(c.left + c.right).equations)
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
    into = sp.Add(*(e.I[t] for e, t, p in c.ends() if p == a))
    end = Origin("end", None)
    laws = c.laws_except((a, b)).equations
    return [*laws, Equation(U - (a.potential - b.potential), end), Equation(I - into, end)]


def _solved(said: list[Equation], letters: set[sp.Symbol]) -> Known:
    """What ``said`` gives, in ``letters``; nothing when it cannot be worked out so."""
    unknowns = frozenset({s for q in said for s in q.expr.free_symbols} - letters)
    try:
        worlds, _ = Problem(unknowns, frozenset(), DC(), {}).solve(said)
    except (Undetermined, NotLinear):
        return {}
    return worlds[0][0]
