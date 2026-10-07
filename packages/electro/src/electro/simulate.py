"""A circuit in time, a coalgebra: Φ takes a frame to the next (``phi(frame, dt)``), and a run is Φ unfolded
from rest (``simulate``). ``Machine`` is the same unfolding compiled to numbers, with a memory of its own.

Φ is the frame formula at a step of ``dt`` with letters for what it learns only as it runs: the step's
length, the time, how a change is read (θ), what was a step before (``memory``: each letter and what it is
after a step) and what the world sets (an element's ``inputs``, set as ``Element.setting`` says). Every
named point has a whisper of a conductance to ground: a floating one is never a singular matrix. What is read
of a frame is any quantity, worked out from what was found (``at``); compiled, for the page (``to_json``).
"""

from __future__ import annotations

import bisect
import json
import math
from array import array
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import ClassVar

import sympy as sp

from .circuit.algebra import symbols_in
from .circuit.element import Element
from .circuit.quantities import Quantity, Scaled
from .circuit.time import THETA, TIME, D
from .errors import NotSimulated, ValueNeeded
from .frame.formula import Closed, Formula, close, formula, parameter_values
from .frame.reading import DT, Step, before, interpret, slope
from .numeric.code import Code, Compiled, compile_equations, python, statements
from .numeric.engine import Machine

G_NODE = 1e-12
SAMPLE_DT = 1e-5
"""A step's length in the sample frame whose numbers choose the pivots (``sparse``)."""
PERIOD_STEPS = 40
"""Steps at least in a period of anything in time in the data (a sine, a square wave)."""
STEP = Step(DT, THETA)


class NoSuchInput(KeyError):
    """Nothing in the circuit is set from outside by that name (a switch's, a board's pin)."""

    def __init__(self, name: str, available: list[str]) -> None:
        super().__init__(name)
        self.name, self.available = name, available


@dataclass(frozen=True)
class Kept:
    """A letter Φ remembers: what it is after a step, at rest, and whether it jumps (a flip-flop's state, a
    switch in time) rather than moves."""

    letter: sp.Symbol
    after: sp.Expr
    rest: float = 0.0
    jumps: bool = False


@dataclass
class Frame:
    """The circuit at time ``t``: its unknowns ``x``, and its letters' values ``p``."""

    t: float
    x: list[float]
    p: list[float]


Key = Element | tuple[Element, str] | str
"""An element (its one input), an element and its input's or pin's name, or as text: ``"S_1"``,
``"S_1_closed"``, ``"ARD_1.D13"``."""


@dataclass
class StepFunction:
    """Φ: the frame formula ``left`` of the closed circuit ``c`` compiled (``code``) over its ``letters`` —
    ``dt``, the time, θ, what is ``kept`` (those under ``D`` first: ``moving`` of them) and what the world
    sets (``inputs``: each one's place)."""

    c: Closed
    left: Formula
    code: Compiled
    letters: list[sp.Symbol]
    kept: list[Kept]
    moving: int
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
        """What the engine's ``Machine`` runs, but its code."""
        return {
            "n": len(self.unknowns),
            "initial": self.initial,
            "states": [3 + k for k in range(len(self.kept))],
            "changing": list(range(self.moving)),
            "jumps": [k for k, st in enumerate(self.kept) if st.jumps],
            "longest": _longest(self.left.laws.expressions()),
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
        """``q`` — a quantity, or an expression in its elements' own variables — in the unknowns and letters."""
        e = self.c.names.of(q) if isinstance(q, Quantity | Scaled) else self.c.names.rename(q)
        return self.left.laws.resolve(e.xreplace(self.left.given))

    def value(self, frame: Frame, q: Quantity | Scaled | sp.Expr) -> float:
        """``q`` in ``frame``."""
        known = dict(zip(self.code.unknowns, frame.x)) | dict(zip(self.letters, frame.p))
        return float(self.at(q).xreplace(known))

    def to_json(self, reads: Mapping[str, sp.Expr] | None = None) -> str:
        """For the page's engine (``simulation/engine.ts``); ``reads``: what it reads of a frame, by name, in
        the elements' own variables (``see`` works them out)."""
        reads = reads or {}
        see = statements(
            [(f"out[{k}]", self.at(e)) for k, e in enumerate(reads.values())], self.code.unknowns, self.letters
        )
        return json.dumps(
            {
                **self.program(),
                "unknowns": self.unknowns,
                "params": self.params,
                "constant": self.code.constant["js"],
                "moving": self.code.moving["js"],
                "shape": self.code.shape,
                "update": self.after["js"],
                "seen": list(reads),
                "see": see["js"],
            }
        )

    def setter(self, key: Key) -> Callable[[object], list[tuple[int, float]]]:
        """What setting ``key`` sets (as its element's ``setting`` says): each letter's place, and its value."""
        labels = self.c.names.labels
        by_label = {label: e for e, label in labels.items()}
        named = {f"{labels[e]}_{w}": (e, w) for e in labels for w in e.inputs}
        label, _, pin = key.partition(".") if isinstance(key, str) else ("", "", "")
        match key:
            case Element() if len(key.inputs) == 1:
                e, which = key, key.inputs[0]
            case (Element() as e, str(which)):
                pass
            case str() if pin and label in by_label:
                e, which = by_label[label], pin
            case str() if key in by_label and len(by_label[key].inputs) == 1:
                e, which = by_label[key], by_label[key].inputs[0]
            case str() if key in named:
                e, which = named[key]
            case _:
                raise NoSuchInput(str(key), sorted(named))

        def setting(value: object) -> list[tuple[int, float]]:
            letters = {f"{labels[e]}_{w}": v for w, v in e.setting(which, value).items()}
            if not set(letters) <= set(self.inputs):
                raise NoSuchInput(str(key), sorted(named))
            return [(self.inputs[w], v) for w, v in letters.items()]

        return setting


def step_function(circuit: Element, values: Mapping) -> StepFunction:
    """Φ: the circuit's frame formula at a step of ``dt``, what was a step before, the time and what the world
    sets letters, compiled."""
    c = close(circuit, leak=G_NODE)
    if several := [e for e in circuit.members if e.rel.laws.choices]:
        raise NotSimulated(several[0].name or several[0].kind)
    given = parameter_values(circuit, values, c.names)
    world = {
        e.P[w].xreplace(c.names.to): sp.Symbol(f"{c.names.labels[e]}_{w}") for e in circuit.members for w in e.inputs
    }
    left = formula(c, STEP, {**given, **world}, keep=c.points)
    if left.params:
        raise ValueNeeded(min(p.name for p in left.params))
    kept = memory(c, left)
    letters = [DT, TIME, THETA, *(k.letter for k in kept), *world.values()]
    exprs = [q.expr for q in left.laws.equations]
    _check_square(exprs, list(left.unknowns), letters)
    initial = [0.0, 0.0, 1.0, *(k.rest for k in kept), *(float(given[p]) for p in world)]
    potentials = [v for v in c.names.to.values() if str(v).startswith("V_")]
    currents = [v for s in left.laws.log for v in s.values]
    code = compile_equations(
        exprs, list(left.unknowns), letters, potentials, currents=currents, sample=[SAMPLE_DT, 0.0, *initial[2:]]
    )
    after = statements([(f"out[{k}]", st.after) for k, st in enumerate(kept)], code.unknowns, letters)
    inputs = {letter.name: 3 + len(kept) + k for k, letter in enumerate(world.values())}
    return StepFunction(c, left, code, letters, kept, len(c.remembered[0]), inputs, initial, after)


def memory(c: Closed, left: Formula) -> list[Kept]:
    """What is remembered, from rest: each quantity under ``D`` (first) or ``Pre``, as what is found has it
    (one only under ``Pre`` and worked out through a ``when`` jumps); of each under ``D`` how fast it changed at
    the step's end, for the next to go by trapezoids; and each switch in time in the data."""
    under_d, under_pre = c.remembered

    def found(e: sp.Expr) -> sp.Expr:
        return left.laws.resolve(e.xreplace(left.given))

    order = [*sorted(under_d, key=str), *sorted(under_pre - under_d, key=str)]
    kept = [Kept(before(x), u := found(x), 0.0, x not in under_d and u.has(sp.Piecewise)) for x in order]
    kept += [Kept(slope(x), found(interpret(D(x), STEP))) for x in sorted(under_d, key=str)]
    edges = sorted(
        {p for e in left.laws.expressions() for p in e.atoms(sp.Piecewise) if symbols_in(p) == {TIME}}, key=str
    )
    return kept + [Kept(sp.Symbol(f"edge{k}"), p, float(p.subs(TIME, 0)), True) for k, p in enumerate(edges)]


def _longest(exprs: list[sp.Expr]) -> float | None:
    """The longest a step may be: ``PERIOD_STEPS`` in a period of each sine and square wave in time."""
    timed = [a for e in exprs for a in e.atoms(sp.sin, sp.cos, sp.Mod) if TIME in a.free_symbols]
    periods = [
        abs(float(a.args[1] / sp.diff(a.args[0], TIME)))
        if isinstance(a, sp.Mod)
        else 2 * math.pi / abs(float(sp.diff(a.args[0], TIME)))
        for a in timed
    ]
    return min(periods) / PERIOD_STEPS if periods else None


def _check_square(exprs: list[sp.Expr], unknowns: list[sp.Symbol], letters: list[sp.Symbol]) -> None:
    """Every symbol a letter or found, and as many laws as unknowns."""
    stray = sorted({x for e in exprs for x in symbols_in(e)} - set(unknowns) - set(letters), key=str)
    if stray:
        raise ValueNeeded(stray[0].name)
    if len(exprs) != len(unknowns):
        raise NotSimulated(f"{len(exprs)} laws, {len(unknowns)} unknowns")


# Unfolded

Schedule = Callable[[float], list[tuple[int, float]]]
"""What the world sets at a time: ``[(letter's place, value)]``."""


def schedule(phi: StepFunction, inputs: Mapping[Key, object] | None) -> Schedule | None:
    """``inputs`` — each a value or a function of time — as what the world sets at a time."""
    if not inputs:
        return None
    setters = [(phi.setter(key), value) for key, value in inputs.items()]
    return lambda now: [pair for set_, value in setters for pair in set_(value(now) if callable(value) else value)]


Runner = Callable[[StepFunction, float, float, "Schedule | None"], "tuple[list[float], array, array] | None"]

RUNNER: Runner | None = None
"""What runs the frames instead of the engine here, when something faster is at hand (the page's engine, the
same printed as JavaScript): the times, the unknowns and the letters of every frame; None: nothing is."""


def simulate(
    circuit: Element, values: Mapping, until: float, dt: float | None = None, inputs: Mapping[Key, object] | None = None
) -> Trace:
    """``until`` seconds from rest. ``dt``: the longest step (by default ``until``/500; steps shrink by
    themselves to keep their error small). ``inputs``: what the world sets, each a value or a function of time."""
    phi = step_function(circuit, values)
    when = schedule(phi, inputs)
    dt_max = dt or until / 500
    if RUNNER is not None and (ran := RUNNER(phi, until, dt_max, when)) is not None:
        return Trace(phi, *ran)
    times: list[float] = []
    rows, params = array("d"), array("d")

    def record(machine: Machine) -> None:
        times.append(machine.t)
        rows.extend(machine.x)
        params.extend(machine.p)

    phi.machine().run(until, dt_max, when, record)
    return Trace(phi, times, rows, params)


@dataclass
class Trace:
    """What happened in a run: the time of each frame, its unknowns (``data``) and its letters (``params``) —
    8 bytes a number (Pyodide's memory never shrinks back)."""

    phi: StepFunction
    t: list[float]
    data: array
    params: array

    reads: ClassVar[Callable[[str, StepFunction], sp.Expr] | None] = None
    """How a name not an unknown's nor a letter's is read (``"I_Q_1_c"``), when something reads names (the
    notebook): as an expression in the elements' own variables."""

    def __call__(self, q: Quantity | Scaled | sp.Expr | str) -> list[float]:
        """``q`` at each frame: a quantity, an expression in the elements' own variables, or a name (an
        unknown's, a letter's; others as ``Trace.reads`` reads them)."""
        if isinstance(q, str):
            if q in self.phi.unknowns or q in self.phi.params:
                return self._column(q)
            if Trace.reads is None:
                raise KeyError(q)
            q = Trace.reads(q, self.phi)
        e = self.phi.at(q)
        xs = sorted(symbols_in(e), key=str)
        f = sp.lambdify(xs, e, "math")
        columns = [self._column(x.name) for x in xs]
        return [float(f(*row)) for row in zip(*columns)] if xs else [float(e)] * len(self.t)

    def at(self, q: Quantity | Scaled | sp.Expr | str, t: float) -> float:
        """``q`` at ``t``: between two frames, on the line between them."""
        k = bisect.bisect_right(self.t, t) - 1
        ys = self(q)
        if k < 0 or k + 1 >= len(self.t) or self.t[k] == t:
            return ys[min(max(k, 0), len(ys) - 1)]
        f = (t - self.t[k]) / (self.t[k + 1] - self.t[k])
        return ys[k] + f * (ys[k + 1] - ys[k])

    def _column(self, name: str) -> list[float]:
        phi = self.phi
        if name in phi.unknowns:
            return self.data[phi.unknowns.index(name) :: len(phi.unknowns)].tolist()
        return self.params[phi.params.index(name) :: len(phi.params)].tolist()
