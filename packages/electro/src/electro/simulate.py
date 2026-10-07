"""A circuit in time. ``step_function`` compiles the circuit's laws at a step of ``dt`` once (Φ); ``phi(frame,
dt)`` gives the next frame, and ``simulate`` runs frame after frame from rest (the engine's ``Machine``).

Φ has letters for what it learns only while it runs: the step's length ``dt``, the time, how a change is read
(θ), what was a step before (``memory``: each letter and its value after a step) and what is set from
outside (an element's ``inputs``). Every point has a tiny conductance to ground, so a floating point never
makes the equations singular. Any quantity can be read of a frame (``at``); the page gets what it reads
compiled (``to_json``)."""

from __future__ import annotations

import bisect
import json
import math
from array import array
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import ClassVar

import sympy as sp

from .circuit import Circuit, Laws, labels, points
from .element import Element
from .elements.physics import pn
from .errors import NoSuchInput, NotSimulated, ValueNeeded
from .frame import DT, Step, before, slope
from .numeric.code import Code, Compiled, compile_equations, python, statements
from .numeric.engine import Machine
from .quantities import Quantity, Scaled
from .solve import references
from .time import THETA, TIME, D, Pre
from .values import given

G_NODE = 1e-12
"""The conductance from every point to ground."""
SAMPLE_DT = 1e-5
"""The step of the sample frame whose numbers choose the pivots (``sparse``)."""
PERIOD_STEPS = 40
"""The fewest steps in a period of a sine or a square wave in the data."""
STEP = Step(DT, THETA)


@dataclass(frozen=True)
class Kept:
    """A letter Φ remembers: its value after a step, at rest, whether it jumps (a flip-flop's state, a switch in
    time) and whether it moves under ``D`` (what a step's error is read from)."""

    letter: sp.Symbol
    after: sp.Expr
    rest: float = 0.0
    jumps: bool = False
    moving: bool = False


@dataclass
class Frame:
    """The circuit at time ``t``: its unknowns ``x`` and its letters' values ``p``."""

    t: float
    x: list[float]
    p: list[float]


Key = Element | tuple[Element, str] | str
"""What an input is named by: an element (its only input), an element and the input's or pin's name, or as
text: ``"S_1"``, ``"S_1_closed"``, ``"ARD_1.D13"``."""


@dataclass
class StepFunction:
    """Φ: the ``circuit``'s ``equations`` at a step of ``dt``, compiled (``code``) over its ``letters``: ``dt``,
    the time, θ, what is ``kept`` and the ``inputs`` (each its letter's place). ``given``: the parameters' values
    and the inputs' letters; ``worked``: unknowns worked out after the frame (``_simple``)."""

    circuit: Circuit
    laws: Laws
    given: dict[sp.Symbol, sp.Expr]
    equations: list[sp.Expr]
    worked: list[tuple[sp.Symbol, sp.Expr]]
    code: Compiled
    letters: list[sp.Symbol]
    kept: list[Kept]
    inputs: dict[str, int]
    initial: list[float]
    after: Code
    _update: Callable | None = field(default=None, repr=False)

    @property
    def unknowns(self) -> list[str]:
        return [u.name for u in self.code.unknowns]

    @property
    def params(self) -> list[str]:
        return [p.name for p in self.letters]

    def update(self, x, p, out) -> None:
        """What is kept, after a step to ``x``."""
        if self._update is None:
            self._update = python(f"def update(x, p, out):\n{self.after['py']}\n")["update"]
        self._update(x, p, out)

    def program(self) -> dict:
        """What the engine's ``Machine`` runs, besides the code."""
        return {
            "n": len(self.unknowns),
            "initial": self.initial,
            "states": [3 + k for k in range(len(self.kept))],
            "changing": [k for k, st in enumerate(self.kept) if st.moving],
            "jumps": [k for k, st in enumerate(self.kept) if st.jumps],
            "longest": _longest(self.equations),
            "inputs": self.inputs,
            "junctions": self.code.junctions,
        }

    def machine(self) -> Machine:
        """Φ with memory: from rest, frame after frame."""
        return Machine(self.program(), self.code.system, self.update)

    @property
    def rest(self) -> Frame:
        """At t = 0, before anything moved: every capacitor empty, every inductor still."""
        return Frame(0.0, [0.0] * len(self.unknowns), list(self.initial))

    def __call__(self, frame: Frame, dt: float) -> Frame | None:
        """The frame ``dt`` after ``frame``; None when Newton does not get there."""
        p = list(frame.p)
        p[0], p[1] = dt, frame.t + dt
        x = self.code.newton(frame.x, p)
        if x is None:
            return None
        after = [0.0] * len(self.kept)
        self.update(x, p, after)
        p[3 : 3 + len(after)] = after
        return Frame(frame.t + dt, x, p)

    def at(self, q: Quantity | Scaled | sp.Expr) -> sp.Expr:
        """``q`` (a quantity, or an expression in the elements' own variables) in the unknowns and letters."""
        e = q.expr if isinstance(q, Quantity | Scaled) else q
        return _put(e.xreplace(dict(self.laws.at)).xreplace(self.given), self.worked)

    def value(self, frame: Frame, q: Quantity | Scaled | sp.Expr) -> float:
        """``q`` in ``frame``."""
        known = dict(zip(self.code.unknowns, frame.x)) | dict(zip(self.letters, frame.p))
        return float(self.at(q).xreplace(known))

    def to_json(self, reads: Mapping[str, sp.Expr] | None = None) -> str:
        """For the page's engine (``simulation/engine.ts``). ``reads``: what the page reads of a frame, by name,
        in the elements' own variables."""
        reads = reads or {}
        see = statements(
            [(f"out[{k}]", self.at(e)) for k, e in enumerate(reads.values())], self.code.unknowns, self.letters
        )
        code = {"constant": self.code.constant["js"], "moving": self.code.moving["js"], "shape": self.code.shape}
        names = {"unknowns": self.unknowns, "params": self.params, "seen": list(reads)}
        return json.dumps({**self.program(), **code, **names, "update": self.after["js"], "see": see["js"]})

    def setter(self, key: Key) -> Callable[[object], list[tuple[int, float]]]:
        """What setting ``key`` sets, as its element's ``setting`` says: each letter's place and value."""
        e, which = self._input(key)
        label = labels(self.circuit)[e]

        def setting(value: object) -> list[tuple[int, float]]:
            letters = {f"{label}_{w}": v for w, v in e.setting(which, value).items()}
            if not set(letters) <= set(self.inputs):
                raise NoSuchInput(str(key), sorted(self.inputs))
            return [(self.inputs[w], v) for w, v in letters.items()]

        return setting

    def _input(self, key: Key) -> tuple[Element, str]:
        """The element and the input (or pin) ``key`` names."""
        named = {label: e for e, label in labels(self.circuit).items()}
        by_letter = {f"{label}_{w}": (e, w) for label, e in named.items() for w in e.inputs}
        label, _, pin = key.partition(".") if isinstance(key, str) else ("", "", "")
        match key:
            case Element() if len(key.inputs) == 1:
                return key, key.inputs[0]
            case (Element() as e, str(which)):
                return e, which
            case str() if pin and label in named:
                return named[label], pin
            case str() if key in named and len(named[key].inputs) == 1:
                return named[key], named[key].inputs[0]
            case str() if key in by_letter:
                return by_letter[key]
        raise NoSuchInput(str(key), sorted(by_letter))


def step_function(circuit: Circuit, values: Mapping) -> StepFunction:
    """Φ: the circuit's laws at a step of ``dt``, compiled once."""
    laws = circuit.closed(leak=G_NODE)
    if laws.ways:
        raise NotSimulated(laws.ways[0][0].element.name or laws.ways[0][0].element.kind)
    known = given(circuit, values)
    inputs = _inputs(circuit)
    letters_in = {**known, **inputs}
    read = STEP.reading(letters_in)
    equations = _equations(laws, read, circuit)
    _all_given(equations, circuit)
    kept = memory(laws, letters_in, read, {x for e in circuit.members for x in e.inner.values()})
    letters = [DT, TIME, THETA, *(k.letter for k in kept), *inputs.values()]
    unknowns = _unknowns(equations, letters)
    equations, worked = _simple(equations, set(unknowns) - _potentials(circuit))
    unknowns = [x for x in unknowns if x not in dict(worked)]
    kept = [Kept(k.letter, _put(k.after, worked), k.rest, k.jumps, k.moving) for k in kept]
    initial = [0.0, 0.0, 1.0, *(k.rest for k in kept), *(float(known[p]) for p in inputs)]
    code = compile_equations(equations, unknowns, letters, sample=[SAMPLE_DT, 0.0, *initial[2:]])
    after = statements([(f"out[{k}]", st.after) for k, st in enumerate(kept)], code.unknowns, letters)
    places = {letter.name: 3 + len(kept) + k for k, letter in enumerate(inputs.values())}
    return StepFunction(circuit, laws, letters_in, equations, worked, code, letters, kept, places, initial, after)


def _inputs(circuit: Circuit) -> dict[sp.Symbol, sp.Symbol]:
    """Each parameter set from outside (``inputs``), and the letter it is in Φ: ``S_1_closed``."""
    label = labels(circuit)
    return {e.P[w]: sp.Symbol(f"{label[e]}_{w}") for e in circuit.members for w in e.inputs}


def _potentials(circuit: Circuit) -> set[sp.Symbol]:
    return {x for p in points(circuit) for x in sp.sympify(p.potential).free_symbols}


def _equations(laws: Laws, read: Callable, circuit: Circuit) -> list[sp.Expr]:
    """The laws at a step, and a reference potential where nothing fixes how high a piece's stand."""
    said = [read(q.expr) for q in laws.equations]
    return said + [q.expr for q in references(said, _potentials(circuit))]


def _all_given(equations: list[sp.Expr], circuit: Circuit) -> None:
    """A simulation needs every parameter's value."""
    params = {x: e for e in circuit.members for x in e.P.values()}
    missing = sorted({x for e in equations for x in e.free_symbols if x in params}, key=str)
    if missing:
        raise ValueNeeded(labels(circuit)[params[missing[0]]])


def _unknowns(equations: list[sp.Expr], letters: list[sp.Symbol]) -> list[sp.Symbol]:
    """What a step finds: every symbol but the letters; as many as there are equations."""
    unknowns = sorted({x for e in equations for x in e.free_symbols} - set(letters), key=str)
    if len(equations) != len(unknowns):
        raise NotSimulated(f"{len(equations)} laws, {len(unknowns)} unknowns")
    return unknowns


def _simple(equations: list[sp.Expr], may_go: set[sp.Symbol]) -> tuple[list[sp.Expr], list[tuple[sp.Symbol, sp.Expr]]]:
    """Each unknown of ``may_go`` an equation gives directly, by a number factor (an element's current by its
    law), worked out after the frame instead of found in it — the removal of simple equations simulators make
    before they run. Points' potentials stay: worked out from one another, a ladder of them would be a
    polynomial in 1/dt of its length."""
    equations, worked = list(equations), []
    for e in list(equations):
        if e in equations and (x := _given_directly(e, may_go)) is not None:
            value = sp.expand(x - e / sp.diff(e, x))
            equations = [f.xreplace({x: value}) for f in equations if f is not e]
            worked.append((x, value))
            may_go.discard(x)
    return equations, worked


def _given_directly(e: sp.Expr, may_go: set[sp.Symbol]) -> sp.Symbol | None:
    """An unknown of ``may_go`` that ``e`` gives with a number factor, outside any function or ``when``."""
    switched = {x for f in e.atoms(sp.Function, sp.Piecewise) for x in f.free_symbols}
    for x in sorted(e.free_symbols & may_go - switched, key=str):
        factor = sp.diff(e, x)
        if factor.is_number and factor != 0:
            return x
    return None


def _put(e: sp.Expr, worked: list[tuple[sp.Symbol, sp.Expr]]) -> sp.Expr:
    """``e`` with each unknown worked out after the frame put in, in order."""
    for x, v in worked:
        if e.has(x):
            e = e.xreplace({x: v})
    return e


def memory(laws: Laws, given: Mapping, read: Callable, inner: set[sp.Symbol]) -> list[Kept]:
    """What Φ remembers, from rest: each quantity under ``D`` (first) or ``Pre`` (an element's inner one only
    under ``Pre`` jumps: a flip-flop's state); for each under ``D``, how fast it changed at the end of the step
    (trapezoids read it); and each switch in time in the data."""
    said = laws.expressions()
    under_d = sorted({a.args[0] for e in said for a in e.atoms(D)}, key=str)
    under_pre = sorted({a.args[0] for e in said for a in e.atoms(Pre)} - set(under_d), key=str)
    kept = [Kept(before(x), x.xreplace(given), moving=True) for x in under_d]
    kept += [Kept(before(x), x.xreplace(given), jumps=x in inner) for x in under_pre]
    kept += [Kept(slope(x), read(D(x))) for x in under_d]
    return kept + _switches(said, read)


def _switches(said: list[sp.Expr], read: Callable) -> list[Kept]:
    """Each ``when`` of time alone in the data (a square wave's edge): remembered, so a step that crosses it
    starts the next short."""
    edges = sorted({p for e in said for p in read(e).atoms(sp.Piecewise) if p.free_symbols == {TIME}}, key=str)
    return [Kept(sp.Symbol(f"edge{k}"), p, float(p.subs(TIME, 0)), True) for k, p in enumerate(edges)]


def _longest(equations: list[sp.Expr]) -> float | None:
    """The longest a step may be: ``PERIOD_STEPS`` in the period of each sine and square wave in time."""
    timed = [a for e in equations for a in e.atoms(sp.sin, sp.cos, sp.Mod) if TIME in a.free_symbols]
    periods = [_period(a) for a in timed]
    return min(periods) / PERIOD_STEPS if periods else None


def _period(a: sp.Expr) -> float:
    rate = abs(float(sp.diff(a.args[0], TIME)))
    return abs(float(a.args[1])) / rate if isinstance(a, sp.Mod) else 2 * math.pi / rate


# Running it

Schedule = Callable[[float], list[tuple[int, float]]]
"""What is set from outside at a time: ``[(letter's place, value)]``."""


def schedule(phi: StepFunction, inputs: Mapping[Key, object] | None) -> Schedule | None:
    """``inputs`` (each a value, or a function of time) as what is set at a time."""
    if not inputs:
        return None
    setters = [(phi.setter(key), value) for key, value in inputs.items()]
    return lambda now: [pair for set_, value in setters for pair in set_(value(now) if callable(value) else value)]


Runner = Callable[[StepFunction, float, float, "Schedule | None"], "tuple[list[float], array, array] | None"]

RUNNER: Runner | None = None
"""Runs the frames instead of the engine here when something faster is at hand (the page's engine, the same
printed as JavaScript): the times, unknowns and letters of every frame; None when it cannot."""


def simulate(
    circuit: Circuit, values: Mapping, until: float, dt: float | None = None, inputs: Mapping[Key, object] | None = None
) -> Trace:
    """``until`` seconds from rest. ``dt``: the longest step (by default ``until``/500; steps shrink by
    themselves to keep their error small). ``inputs``: what is set from outside, each a value or a function of
    time."""
    phi = step_function(circuit, values)
    when = schedule(phi, inputs)
    dt_max = dt or until / 500
    if RUNNER is not None and (ran := RUNNER(phi, until, dt_max, when)) is not None:
        return Trace(phi, *ran)
    trace = Trace(phi, [], array("d"), array("d"))
    phi.machine().run(until, dt_max, when, trace.record)
    return trace


@dataclass
class Trace:
    """A run: the time of each frame, its unknowns (``data``) and its letters (``params``), 8 bytes a number."""

    phi: StepFunction
    t: list[float]
    data: array
    params: array

    reads: ClassVar[Callable[[str, StepFunction], sp.Expr] | None] = None
    """How a name is read (``"I_Q_1_c"``), when something reads names (the notebook): as an expression in the
    elements' own variables."""

    def record(self, machine: Machine) -> None:
        self.t.append(machine.t)
        self.data.extend(machine.x)
        self.params.extend(machine.p)

    def __call__(self, q: Quantity | Scaled | sp.Expr | str) -> list[float]:
        """``q`` at each frame: a quantity, an expression in the elements' own variables, or a name."""
        if isinstance(q, str):
            if Trace.reads is None:
                raise KeyError(q)
            q = Trace.reads(q, self.phi)
        e = self.phi.at(q).replace(lambda a: isinstance(a, pn), lambda a: sp.exp(a.args[0]))
        xs = sorted(e.free_symbols, key=str)
        f = sp.lambdify(xs, e, "math")
        columns = [self._column(x) for x in xs]
        return [float(f(*row)) for row in zip(*columns)] if xs else [float(e)] * len(self.t)

    def at(self, q: Quantity | Scaled | sp.Expr | str, t: float) -> float:
        """``q`` at time ``t``: between two frames, on the line between them."""
        ys = self(q)
        k = bisect.bisect_right(self.t, t) - 1
        if k < 0 or k + 1 >= len(self.t) or self.t[k] == t:
            return ys[min(max(k, 0), len(ys) - 1)]
        f = (t - self.t[k]) / (self.t[k + 1] - self.t[k])
        return ys[k] + f * (ys[k + 1] - ys[k])

    def _column(self, x: sp.Symbol) -> list[float]:
        """An unknown's or a letter's value at each frame."""
        xs, letters = self.phi.code.unknowns, self.phi.letters
        if x in xs:
            return self.data[xs.index(x) :: len(xs)].tolist()
        return self.params[letters.index(x) :: len(letters)].tolist()
