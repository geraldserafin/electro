"""What elements' laws are made of: equations, each with the reason it holds, and ``Laws`` — what holds of a
piece, a monoid under ``&`` (both hold). ``Laws`` is three things at once: the equations; the elements of
several ways (each choice: one of its ways holds — the list monad, kept factored until a frame is solved);
and the log (a Writer's): every variable that went, its value and why. The log is at once the steps a book
shows and the way back to every quantity that went.

One operation does the work: ``eliminate`` — while some equation gives a variable alone, that variable goes
everywhere, its value logged. Joining pieces hides what they share by it; solving by hand finds the unknowns
one by one by it; the two differ only in when a variable is alone."""

from __future__ import annotations

from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass
from typing import cast

import sympy as sp

from .time import DT, THETA


@dataclass(frozen=True)
class Origin:
    """Where an equation comes from, the reason a step gives: ``what`` is ``"law"`` (an element's
    ``index``-th; ``case``: the way it then is), ``"kcl"`` (Kirchhoff at a point), ``"wire"`` (two ends
    joined), ``"given"`` (a datum), ``"reference"`` (a potential chosen 0), ``"assumed"`` or ``"holds"``;
    ``subject``: the element, the point, the datum's key."""

    what: str
    subject: object
    index: int = 0
    case: str = ""


@dataclass(frozen=True)
class Equation:
    """``expr`` = 0."""

    expr: sp.Expr
    origin: Origin


@dataclass(frozen=True)
class SolutionStep:
    """One entry of the log: what was found, its value, and from which equations (their origins: the
    reason). ``how``: ``"alone"`` (one equation, one unknown), ``"together"`` (several at once),
    ``"numerically"``, ``"assumed"`` (an element taken to be one of its ways), ``"checked"`` (what that way
    needs holds) or ``"rejected"``."""

    found: tuple[sp.Symbol, ...]
    values: tuple[sp.Expr, ...]
    because: tuple[Origin, ...]
    how: str = "alone"
    equations: tuple[sp.Expr, ...] = ()
    """Each origin's equation (= 0), as it was."""


@dataclass(frozen=True)
class Case:
    """One way an element may be (a diode on, or off): its laws then, and what must hold for it to be that
    way, each ``holds`` ≥ 0."""

    name: str
    laws: tuple[sp.Expr, ...]
    holds: tuple[sp.Expr, ...] = ()


@dataclass(frozen=True)
class Cases:
    """An element of several ways (piecewise: the textbook's diode). The circuit decides which: the one
    whose ``holds`` hold."""

    cases: tuple[Case, ...]


@dataclass(frozen=True)
class Way:
    """One way an element may be, within a circuit: its equations then, and what must hold (≥ 0)."""

    element: object
    name: str
    equations: tuple[Equation, ...]
    holds: tuple[sp.Expr, ...]


Known = dict[sp.Symbol, sp.Expr]


@dataclass(frozen=True)
class Laws:
    equations: tuple[Equation, ...] = ()
    choices: tuple[tuple[Way, ...], ...] = ()
    log: tuple[SolutionStep, ...] = ()

    def __and__(self, other: Laws) -> Laws:
        return Laws(self.equations + other.equations, self.choices + other.choices, self.log + other.log)

    def map(self, f: Callable[[sp.Expr], sp.Expr]) -> Laws:
        """Every expression through ``f`` (a renaming, values put in, a frame's reading)."""

        def eq(q: Equation) -> Equation:
            return Equation(f(q.expr), q.origin)

        def step(s: SolutionStep) -> SolutionStep:
            return SolutionStep(
                tuple(cast(sp.Symbol, f(x)) for x in s.found),
                tuple(map(f, s.values)),
                s.because,
                s.how,
                tuple(map(f, s.equations)),
            )

        return Laws(
            tuple(map(eq, self.equations)),
            tuple(
                tuple(Way(w.element, w.name, tuple(map(eq, w.equations)), tuple(map(f, w.holds))) for w in c)
                for c in self.choices
            ),
            tuple(map(step, self.log)),
        )

    def expressions(self) -> list[sp.Expr]:
        """Every expression in it: what it says."""
        out: list[sp.Expr] = []
        self.map(lambda e: out.append(e) or e)
        return out

    def resolve(self, e: sp.Expr) -> sp.Expr:
        """``e`` in what is left: each variable that went by its value, in order."""
        for s in self.log:
            for x, v in zip(s.found, s.values):
                if e.has(x):
                    e = e.xreplace({x: v})
        return sp.expand(e, power_exp=False)

    def complete(self, found: Mapping[sp.Symbol, sp.Expr] = {}) -> Known:  # noqa: B006
        """Every variable that went, from what was found: the last first."""
        out = dict(found)
        for s in reversed(self.log):
            for x, value in zip(s.found, s.values):
                v = value.xreplace(out)
                out[x] = normal(v) if v.free_symbols else v
        return out

    def found(self) -> Known:
        """What the log found, as it found it."""
        return {x: v for s in self.log for x, v in zip(s.found, s.values)}

    def put(self, values: Mapping[sp.Symbol, sp.Expr], step: SolutionStep) -> Laws:
        """``values`` put in everywhere (the equations, the ways and what they need), and ``step`` logged."""

        def put(e: sp.Expr) -> sp.Expr:
            return normal(e.xreplace(values)) if any(e.has(x) for x in values) else e

        laws = Laws(self.equations, self.choices).map(put)
        return Laws(tuple(q for q in laws.equations if q.expr != 0), laws.choices, (*self.log, step))

    def take(self, q: Equation, x: sp.Symbol, value: sp.Expr) -> Laws:
        """``x`` = ``value``, as ``q`` says: ``q`` used up, ``x`` gone everywhere."""
        rest = Laws(tuple(p for p in self.equations if p is not q), self.choices, self.log)
        return rest.put({x: value}, SolutionStep((x,), (value,), (q.origin,), equations=(q.expr,)))

    def eliminate(self, xs: Collection[sp.Symbol], rule: Rule, keep: Collection[sp.Symbol] = ()) -> Laws:
        """Every one of ``xs`` (but ``keep``) that an equation gives alone by ``rule``, gone: ``many (alone
        …)``, the one way it goes."""
        (out,) = many(alone(set(xs) - set(keep), rule))(self)
        return out


# Solving as parsing. A ``Solve`` takes what is left (``Laws``: its equations are a parser's input) to every
# way it can go on — a list: an element of several ways, several roots. A way that cannot go on ends in a
# ``"rejected"`` step and stays in the list, so the tries are steps (the log is shared through the search:
# ``ListT (Writer Log)``). The combinators are a parser's: ``then`` (*>), ``each`` (<|>, every way), ``many``,
# ``alone`` (``satisfy``: one equation gives one variable).

Solve = Callable[[Laws], list[Laws]]
Step = Callable[[Laws], list[Laws] | None]
"""One step, or None: nothing to take."""
Rule = Callable[[sp.Expr, sp.Symbol], list[sp.Expr] | None]
"""The values ``x`` has by ``e`` = 0 ([]: none, a contradiction), or None: not alone there."""


def failed(laws: Laws) -> bool:
    return bool(laws.log) and laws.log[-1].how == "rejected"


def rejected(laws: Laws, because: Origin) -> Laws:
    return Laws(laws.equations, laws.choices, (*laws.log, SolutionStep((), (), (because,), "rejected")))


def then(*solves: Solve) -> Solve:
    """Each in turn, on every way the one before left."""

    def run(laws: Laws) -> list[Laws]:
        out = [laws]
        for solve in solves:
            out = [m for k in out for m in ([k] if failed(k) else solve(k))]
        return out

    return run


def each(*solves: Solve) -> Solve:
    """Every way any of them goes."""
    return lambda laws: [m for solve in solves for m in solve(laws)]


def many(step: Step) -> Solve:
    """``step`` again and again, while it takes something."""

    def run(laws: Laws) -> list[Laws]:
        took = None if failed(laws) else step(laws)
        return [laws] if took is None else [m for k in took for m in run(k)]

    return run


def alone(xs: set[sp.Symbol], rule: Rule) -> Step:
    """One equation that gives one of ``xs`` alone by ``rule`` (the fewest of ``xs`` first; what only joins
    first; never one under a function — ``exp``, a time word: what is tangled stays): it goes. Several values
    wait for the rest; none is a contradiction."""

    def step(laws: Laws) -> list[Laws] | None:
        tangled = {x for q in laws.equations for f in q.expr.atoms(sp.Function) for x in symbols_in(f)}
        for q in sorted(laws.equations, key=lambda q: len(symbols_in(q.expr) & xs)):
            for x in sorted(symbols_in(q.expr) & xs - tangled, key=_joining_first):
                values = rule(q.expr, x)
                if values == []:
                    return [rejected(laws, q.origin)]
                if values is not None and len(values) == 1:
                    return [laws.take(q, x, values[0])]
        return None

    return step


JOINING: set[sp.Symbol] = set()
"""What only joins (a point's, a crossing's variables): the first to go."""


def _joining_first(x: sp.Symbol) -> tuple[bool, str]:
    return x not in JOINING, str(x)


def linear(held: Collection[sp.Symbol], steady: Callable[[sp.Expr], bool]) -> Rule:
    """``x`` alone in an equation of degree one in it whose factor holds none of ``held``, is ``steady``
    (never 0 as the circuit runs) and is not 0: how joining hides a variable."""

    def rule(e: sp.Expr, x: sp.Symbol) -> list[sp.Expr] | None:
        a = sp.diff(e, x)
        if a.has(x) or symbols_in(a) & set(held) or not steady(a) or sp.expand(a) == 0:
            return None
        return [normal(-(e - a * x) / a)]

    return rule


def ways(laws: Sequence[sp.Expr] | Cases) -> tuple[Case, ...]:
    """Laws as ways: plain laws are one way, of no name."""
    if isinstance(laws, Cases):
        return tuple(Case(c.name, tuple(map(expr, c.laws)), tuple(map(expr, c.holds))) for c in laws.cases)
    return (Case("", tuple(map(expr, laws))),)


def normal(e: sp.Expr) -> sp.Expr:
    """An expression as short as it cheaply gets: over one denominator, cancelled, when a letter divides it
    (0 then when it always is; the denominator kept — cleared, its zeros would be roots that are none);
    expanded otherwise, an exponential of a sum never split into a product (e^(u−5) as e^u·e^−5: one huge,
    one tiny). A frame's length and how it reads a change never: x/dt is 0 in a frame infinitely long, x·dt/dt is not."""
    if e.atoms(sp.Function) or not any(
        p.exp.is_negative and p.base.free_symbols - {DT, THETA} for p in e.atoms(sp.Pow)
    ):
        return sp.expand(e, power_exp=False)
    return sp.cancel(e)


def expr(x: object) -> sp.Expr:
    return cast(sp.Expr, sp.sympify(x))


def subs(x: sp.Expr, values: Mapping[sp.Symbol, sp.Expr] | Mapping[sp.Symbol, float]) -> sp.Expr:
    return cast(sp.Expr, x.subs(list(values.items())))


def symbols_in(x: object) -> set[sp.Symbol]:
    return {s for s in expr(x).free_symbols if isinstance(s, sp.Symbol)}
