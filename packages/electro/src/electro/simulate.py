"""A circuit in time: Φ, its step function — the frame formula read at a step of ``dt``, what was a step
before, the time and what the world sets (a switch, a pin) its letters — compiled once, then run frame after
frame from rest, each step as long as what is remembered allows (``engine``).

What is remembered is what the laws keep under ``D`` and ``Pre``. Every named point has a whisper of a
conductance to ground: a floating one is never a singular matrix.
"""

from __future__ import annotations

import bisect
import importlib
import json
import math
import sys
from array import array
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import cast

import sympy as sp

from .circuit.algebra import expr, subs, symbols_in
from .circuit.element import Element
from .circuit.quantities import Quantity, Scaled
from .circuit.time import THETA, TIME, D
from .errors import NotSimulated, ValueNeeded
from .frame.formula import Formula, NotClosed, formula, names, parameter_values
from .frame.reading import DT, Step, before, interpret, slope
from .numeric.code import Code, Compiled, compile_equations, python, statements
from .numeric.engine import Machine, NoConvergence

G_NODE = 1e-12
SAMPLE_DT = 1e-5
"""A step's length in the sample frame whose numbers choose the pivots (``sparse``)."""
PERIOD_STEPS = 40
"""Steps at least in a period of anything in time in the data (a sine, a square wave)."""


class NoSuchInput(KeyError):
    """Nothing in the circuit is set from outside by that name (a switch's, a board's pin)."""

    def __init__(self, name: str, available: list[str]) -> None:
        super().__init__(name)
        self.name, self.available = name, available


@dataclass
class Frame:
    """The circuit at time ``t``: its unknowns ``x``, and the step's parameters ``p`` — ``dt``, ``t``, what
    is remembered, what the world sets."""

    t: float
    x: list[float]
    p: list[float]


@dataclass
class StepFunction:
    """Φ. ``equations``: a step's, over its unknowns; its parameters ``dt``, the time at the step's end, what
    is remembered and what the world sets. ``states``: each remembered value's parameter, ``changing`` the
    places in ``states`` of what changes (under ``D``), ``jumps`` those that jump, ``longest`` the longest a
    step may be; ``update`` fills what is remembered after a step. ``seen``: what is read
    of a frame, by name — each point's potential, each element's voltage, currents and what its kind shows —
    worked out straight from the unknowns by ``see``; ``nodes``, ``parts`` and ``flows`` (each terminal's
    current, into its element) say where in it the page finds a point and an element."""

    circuit: Element
    left: Formula
    equations: Compiled
    initial: list[float]
    states: list[int]
    changing: list[int]
    jumps: list[int]
    longest: float | None
    inputs: dict[str, int]
    update_body: Code
    seen: dict[str, sp.Expr]
    see_body: Code
    nodes: dict[str, int]
    parts: dict[str, dict[str, int]]
    kinds: dict[str, str]
    flows: dict[str, list[int]]
    _compiled: tuple | None = field(default=None, repr=False)

    @property
    def unknowns(self) -> list[str]:
        return [u.name for u in self.equations.unknowns]

    @property
    def params(self) -> list[str]:
        return [p.name for p in self.equations.params]

    def functions(self):
        """The update and what is seen as Python functions."""
        if self._compiled is None:
            scope = python(
                f"def update(x, p, out):\n{self.update_body['py']}\n\ndef see(x, p, out):\n{self.see_body['py']}\n"
            )
            self._compiled = (scope["update"], scope["see"])
        return self._compiled

    def read(self, frame: Frame) -> dict[str, float]:
        """What is seen of ``frame``, by name."""
        out = [0.0] * len(self.seen)
        self.functions()[1](frame.x, frame.p, out)
        return dict(zip(self.seen, out))

    def machine(self) -> Machine:
        """Φ with memory: from rest, frame after frame."""
        return Machine(self.program(), self.equations.system, self.functions()[0])

    def program(self) -> dict:
        """What the engine's ``Machine`` runs, but its code."""
        return {
            "n": len(self.unknowns),
            "initial": self.initial,
            "states": self.states,
            "changing": self.changing,
            "jumps": self.jumps,
            "longest": self.longest,
            "inputs": self.inputs,
            "junctions": self.equations.junctions,
        }

    @property
    def rest(self) -> Frame:
        """At t = 0, before anything moved: every capacitor empty, every inductor still."""
        return Frame(0.0, [0.0] * len(self.unknowns), list(self.initial))

    def __call__(self, frame: Frame, dt: float) -> Frame | None:
        """The frame ``dt`` after ``frame``; None when Newton does not get there."""
        p = list(frame.p)
        p[0], p[1] = dt, frame.t + dt
        x = self.equations.newton(frame.x, p)
        if x is None:
            return None
        after = [0.0] * len(self.states)
        self.functions()[0](x, p, after)
        for i, v in zip(self.states, after):
            p[i] = v
        return Frame(frame.t + dt, x, p)

    def at(self, q: Quantity | Scaled) -> sp.Expr:
        """``q`` in the unknowns and parameters."""
        return self.left.laws.resolve(self.left.names.of(q))

    def to_json(self) -> str:
        """For the page's engine (``simulation/engine.ts``)."""
        return json.dumps(
            {
                **self.program(),
                "unknowns": self.unknowns,
                "params": self.params,
                "constant": self.equations.constant["js"],
                "moving": self.equations.moving["js"],
                "shape": self.equations.shape,
                "update": self.update_body["js"],
                "seen": list(self.seen),
                "see": self.see_body["js"],
                "nodes": self.nodes,
                "parts": self.parts,
                "kinds": self.kinds,
                "flows": self.flows,
            }
        )


@dataclass(frozen=True)
class _State:
    symbol: sp.Symbol
    update: sp.Expr
    initial: float = 0.0
    jumps: bool = False


def step_function(circuit: Element, values: Mapping) -> StepFunction:
    """The circuit's frame formula at a step of ``dt``, what was a step before, the time and what the world
    sets letters, compiled."""
    if circuit.free != (0, 0):
        raise NotClosed(*circuit.free)
    for e in circuit.members:
        if e.rel.laws.choices:
            raise NotSimulated(e.name or e.kind)
    n = names(circuit)
    labels = n.labels
    given = parameter_values(circuit, values, n)
    inputs = [
        (e.P[w].xreplace(n.to), sp.Symbol(f"{labels[e]}_{w}"), float(given[e.P[w].xreplace(n.to)]))
        for e in circuit.members
        for w in e.inputs
    ]
    letters = {param: letter for param, letter, _ in inputs}
    left = formula(circuit, values, Step(DT, THETA), kept=True, letters=letters, leak=G_NODE)
    if left.params:
        raise ValueNeeded(min(p.name for p in left.params))
    exprs = [q.expr for q in left.laws.equations]
    unknowns = list(left.unknowns)
    memory, changing = _memory(left, {**given, **letters})
    edges = sorted(
        {p for e in left.laws.expressions() for p in e.atoms(sp.Piecewise) if symbols_in(p) == {TIME}}, key=str
    )
    states = memory + [_State(sp.Symbol(f"edge{k}"), p, float(p.subs(TIME, 0)), True) for k, p in enumerate(edges)]
    params = [DT, TIME, THETA, *(st.symbol for st in states), *(letter for _, letter, _ in inputs)]
    parts = _observed(circuit, left)
    flowing = {f"{labels[e]}.{t}": c.xreplace(left.names.to) for e in circuit.members for t, c in e.I.items()}
    seen = {str(v): v for v in left.names.points.values()}
    seen |= {called: value for named in parts.values() for called, value in named.values()} | flowing
    seen = {name: left.laws.resolve(expr(value)) for name, value in seen.items()}
    _check_square([*exprs, *seen.values()], unknowns, params, len(exprs))
    potentials = [v for v in left.names.to.values() if str(v).startswith("V_")]
    initial = [0.0, 0.0, 1.0, *(st.initial for st in states), *(value for _, _, value in inputs)]
    sample = [SAMPLE_DT, 0.0, *initial[2:]]
    currents = [v for s in left.laws.log for v in s.values]
    compiled = compile_equations(exprs, unknowns, params, potentials, currents=currents, sample=sample)
    unknowns = compiled.unknowns
    place = {name: k for k, name in enumerate(seen)}
    return StepFunction(
        circuit=circuit,
        left=left,
        equations=compiled,
        initial=initial,
        states=[3 + k for k in range(len(states))],
        changing=changing,
        jumps=[k for k, st in enumerate(states) if st.jumps],
        longest=_longest(left.laws.expressions()),
        inputs={letter.name: 3 + len(states) + k for k, (_, letter, _) in enumerate(inputs)},
        update_body=statements([(f"out[{k}]", st.update) for k, st in enumerate(states)], unknowns, params),
        seen=seen,
        see_body=statements([(f"out[{k}]", v) for k, v in enumerate(seen.values())], unknowns, params),
        nodes={str(v)[2:]: place[str(v)] for v in left.names.points.values()},
        parts={label: {name: place[called] for name, (called, _) in named.items()} for label, named in parts.items()},
        kinds={labels[e]: e.kind for e in circuit.members},
        flows={labels[e]: [place[f"{labels[e]}.{t}"] for t in e.terminals] for e in circuit.members},
    )


def _memory(left: Formula, values) -> tuple[list[_State], list[int]]:
    """What is remembered, from rest: each quantity under ``D`` or ``Pre``, after a step as what is found then
    has it (one only under ``Pre`` and worked out through a ``when`` jumps: a flip-flop's state); of each under
    ``D``, how fast it changed at the end of the step too, for the next to go by trapezoids. And the places
    of those under ``D``: what a step's error is read off."""
    under_d, under_pre = left.remembered
    kept = sorted(under_d | under_pre, key=str)
    states = [
        _State(before(x), u := left.laws.resolve(subs(x, values)), 0.0, x not in under_d and u.has(sp.Piecewise))
        for x in kept
    ]
    changing = sorted(under_d, key=str)
    states += [_State(slope(x), left.laws.resolve(subs(interpret(D(x), Step(DT, THETA)), values))) for x in changing]
    return states, [kept.index(x) for x in changing]


def _observed(circuit: Element, left: Formula) -> dict[str, dict[str, tuple[str, sp.Expr]]]:
    """What the page reads of each element, by name, and what it is called: ``U``, ``I`` of two terminals,
    ``I_<terminal>`` of more, its inner quantities, and what its kind ``shows``."""
    to, labels = left.names.to, left.names.labels
    out = {}
    for e in circuit.members:
        label = labels[e]

        def across(a: str, b: str, e=e) -> sp.Expr:
            return (e.V[a] - e.V[b]).xreplace(to)

        named: dict[str, tuple[str, sp.Expr]] = {}
        if len(e.terminals) == 2:
            a, b = e.terminals
            named["I"] = (f"I_{label}", e.I[a].xreplace(to))
            named["U"] = (f"U_{label}", across(a, b))
        else:
            ends = e.terminals[:-1] if e.ground else e.terminals
            named |= {f"I_{t}": (f"I_{label}_{t}", e.I[t].xreplace(to)) for t in ends}
        named |= {name: (f"{name}_{label}", x.xreplace(to)) for name, x in e.inner.items()}
        for name, what in e.shows:
            value = e.I[what].xreplace(to) if isinstance(what, str) else across(*what)
            named[name] = (f"{name[0]}_{label}{name[1:]}", value)
        out[label] = named
    return out


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


def _check_square(exprs: list[sp.Expr], unknowns: list[sp.Symbol], params: list[sp.Symbol], laws: int) -> None:
    """Every symbol a value or found, and as many ``laws`` (the first of ``exprs``) as unknowns."""
    allowed = set(unknowns) | set(params)
    stray = sorted({x for e in exprs for x in symbols_in(e)} - allowed, key=str)
    if stray:
        raise ValueNeeded(stray[0].name)
    if laws != len(unknowns):
        raise NotSimulated(f"{laws} laws, {len(unknowns)} unknowns")


# Frame after frame

Schedule = Callable[[float], list[tuple[int, float]]]
"""What the world sets at a time: ``[(param index, value)]``."""


def run(phi: StepFunction, until: float, dt_max: float, schedule: Schedule | None = None, on_frame=None) -> Machine:
    """From rest to ``until`` (``Machine.run``); ``on_frame`` gets the machine at every frame."""
    machine = phi.machine()
    machine.run(until, dt_max, schedule, on_frame)
    return machine


# What the world sets

Key = Element | tuple[Element, str] | str
"""An element (its one input), an element and its input's or its pin's name, or that as text:
``"S_1"``, ``"S_1_closed"``, ``"ARD_1.D13"``."""


def schedule(phi: StepFunction, inputs: Mapping[Key, object] | None) -> Schedule | None:
    if not inputs:
        return None
    labels = phi.left.names.labels
    parts = [(_setter(phi, _name(key, labels)), value) for key, value in inputs.items()]
    return lambda now: [pair for setter, value in parts for pair in setter(value(now) if callable(value) else value)]


def _name(key: Key, labels) -> str:
    match key:
        case Element():
            return labels[key]
        case (Element() as e, str(which)):
            return f"{labels[e]}.{which}"
    return str(key)


def _kind(phi: StepFunction, label: str) -> Element | None:
    return next((e for e, x in phi.left.names.labels.items() if x == label), None)


def _setter(phi: StepFunction, name: str):
    label, _, pin = name.partition(".")
    e = _kind(phi, label)
    if pin and e is not None and e.modes:
        g, v = f"{label}_{pin}_G", f"{label}_{pin}_E"
        if g in phi.inputs:
            gi, ei = phi.inputs[g], phi.inputs[v]
            modes = e.modes

            def set_mode(mode: object) -> list[tuple[int, float]]:
                conductance, volts = (
                    modes[mode] if isinstance(mode, str) else (modes["high"][0], float(cast(float, mode)))
                )
                return [(gi, conductance), (ei, volts)]

            return set_mode
    whole = _kind(phi, name)
    for candidate in [name, *(f"{name}_{w}" for w in (whole.inputs if whole is not None else ()))]:
        if candidate in phi.inputs:
            index = phi.inputs[candidate]
            return lambda value: [(index, float(cast(float, value)))]
    available = []
    for e, label in phi.left.names.labels.items():
        if e.modes:
            available += [f"{label}.{w[:-2]}" for w in e.inputs if w.endswith("_G")]
        else:
            available += [label] if len(e.inputs) == 1 else [f"{label}_{w}" for w in e.inputs]
    raise NoSuchInput(name, available)


# The run


def simulate(
    circuit: Element, values: Mapping, until: float, dt: float | None = None, inputs: Mapping[Key, object] | None = None
) -> Trace:
    """``until`` seconds from rest. ``dt``: the longest step (by default ``until``/500; steps shrink by
    themselves where things move fast). ``inputs``: what the world sets, each a value or a function of time."""
    phi = step_function(circuit, values)
    when = schedule(phi, inputs)
    dt_max = dt or until / 500
    engine = _engine()
    times: list[float] = []
    rows = array("d")
    if engine is not None:
        return Trace(phi, *_in_the_page(engine, phi, until, dt_max, when))
    params = array("d")

    def record(machine: Machine) -> None:
        times.append(machine.t)
        rows.extend(machine.x)
        params.extend(machine.p)

    run(phi, until, dt_max, when, record)
    return Trace(phi, times, rows, params)


def _engine():
    if sys.platform != "emscripten":
        return None
    return getattr(importlib.import_module("js"), "electroSim", None)


def _in_the_page(engine, phi: StepFunction, until: float, dt_max: float, when):
    create_proxy = importlib.import_module("pyodide.ffi").create_proxy
    callback = create_proxy(lambda now: [list(pair) for pair in when(now)]) if when else None
    try:
        result = engine.run(phi.to_json(), until, dt_max, callback)
    except Exception as err:
        if "NoConvergence" in str(err):
            raise NoConvergence(float(str(err).rsplit(" ", 1)[-1])) from None
        raise
    finally:
        if callback is not None:
            callback.destroy()
    times, rows, params = array("d"), array("d"), array("d")
    times.frombytes(result.t.to_bytes())
    rows.frombytes(result.rows.to_bytes())
    params.frombytes(result.params.to_bytes())
    return times.tolist(), rows, params


@dataclass
class Trace:
    """What happened in a run: the time of each frame, its unknowns (``data``) and its parameters — 8 bytes a
    number (Pyodide's memory never shrinks back)."""

    phi: StepFunction
    t: list[float]
    data: array
    params: array

    def __call__(self, q: Quantity | Scaled | str) -> list[float]:
        """``q`` at each frame: a quantity, or an unknown's or a point's name (``"I_R_1"``, ``"V_A"``)."""
        if isinstance(q, str):
            return self._column(q)
        return self._of(self.phi.at(q))

    def _of(self, e: sp.Expr) -> list[float]:
        names = sorted({s.name for s in e.free_symbols if isinstance(s, sp.Symbol)})
        f = sp.lambdify([sp.Symbol(n) for n in names], e, "math")
        columns = [self._column(n) for n in names]
        return [float(f(*row)) for row in zip(*columns)] if names else [float(e)] * len(self.t)

    def at(self, q: Quantity | Scaled | str, t: float) -> float:
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
        if name in phi.params:
            return self.params[phi.params.index(name) :: len(phi.params)].tolist()
        if name in phi.seen:
            return self._of(phi.seen[name])
        raise KeyError(name)
