"""A problem compiled for running in time: the equations of one step (``Step(dt)``), their Jacobian, and
what moves on between steps, written once as code — Python for ``run``, JavaScript for the page's engine
(``to_json``). Each step is then Newton's method on plain numbers.

What is remembered is what the laws keep under ``D`` and ``Pre``; what the world sets while it runs is
each kind's ``inputs``. Three things help Newton, all of them general, none of them any element's own:
every point has a whisper of a conductance to ground (a floating one is never a singular matrix), every
exponential grows along its tangent far out, and one with a tiny current at zero — a p-n junction —
is approached along it, as SPICE does.
"""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from dataclasses import dataclass, field

import sympy as sp

from ..circuit.elements.modules import LCD_INPUTS
from ..circuit.time import TIME, D, Pre
from ..circuit.tree import Net
from ..problem.problem import Problem
from ..solver.analysis import Step, before, is_before
from ..solver.expressions import expr, subs, symbols_in
from ..solver.laws import inner_names, of_ways
from ..solver.relation import Relation, all_equations
from ..solver.symbols import Symbols, symbols
from ..solver.system import equations, parameter_values, relation
from .code import Code, statements
from .errors import NotSimulated, ValueNeeded
from .functions import limexp, limited_exp, limited_exp_slope

DT = sp.Symbol("dt", positive=True)
G_NODE = 1e-12
STEP_VOLTS, STEP_AMPS = 0.05, 1e-3
"""How far a remembered current may move in one step; a voltage, or anything else."""
SINE_STEPS, EDGE_STEPS = 40, 100
"""Steps at least in a period of a sine, of a square wave."""
JUNCTION = 1e-6
"""An exponential passing less than this at zero is a p-n junction."""

PAGE: dict[str, dict[str, tuple[str, str] | str]] = {
    "servo": {"U_sig": ("sig", "gnd"), "U": ("vcc", "gnd"), "I": "vcc"},
    "ultrasonic": {"U": ("vcc", "gnd"), "U_trig": ("trig", "gnd"), "I": "vcc"},
    "lcd1602": {"U": ("vdd", "vss"), **{f"U_{p}": (p, "vss") for p in ("v0", *LCD_INPUTS)}, "I": "vdd"},
}
"""What the page reads of a kind besides its currents and inner quantities: a voltage between two of its
terminals, or a current into one, by name."""


@dataclass
class Program:
    """``unknowns`` are found each step; ``params`` are ``dt``, the time at the step's end, what is
    remembered and what is set from outside. ``states``: the param index of each remembered value and the
    most it may move in a step (None: it jumps). ``kernel`` fills the residuals and the Jacobian (flat, row by
    row), ``update`` what is remembered after a step, ``flow`` each terminal's current."""

    unknowns: list[str]
    params: list[str]
    initial: list[float]
    states: list[tuple[int, float | None]]
    inputs: dict[str, int]
    junctions: list[tuple[int, float, float]]
    kernel_body: Code
    update_body: Code
    nodes: dict[str, int | None]
    parts: dict[str, dict[str, int]]
    kinds: dict[str, str]
    flow_body: Code
    flows: dict[str, list[int]]
    _compiled: tuple | None = field(default=None, repr=False)

    def functions(self):
        """The kernel, the update and the flow as Python functions."""
        if self._compiled is None:
            scope = {
                "exp": math.exp,
                "limexp": limited_exp,
                "dlimexp": limited_exp_slope,
                **{f: getattr(math, f) for f in ("log", "sqrt", "sin", "cos", "tanh", "floor", "pi")},
            }
            exec(f"def kernel(x, p, F, J):\n{self.kernel_body['py']}\n", scope)
            exec(f"def update(x, p, out):\n{self.update_body['py']}\n", scope)
            exec(f"def flow(x, p, out):\n{self.flow_body['py']}\n", scope)
            self._compiled = (scope["kernel"], scope["update"], scope["flow"])
        return self._compiled

    def to_json(self) -> str:
        """For the page's engine (``simulation/engine.ts``)."""
        return json.dumps(
            {
                "unknowns": self.unknowns,
                "params": self.params,
                "initial": self.initial,
                "states": self.states,
                "inputs": self.inputs,
                "junctions": self.junctions,
                "kernel": self.kernel_body["js"],
                "update": self.update_body["js"],
                "nodes": self.nodes,
                "parts": self.parts,
                "kinds": self.kinds,
                "flow": self.flow_body["js"],
                "flows": self.flows,
            }
        )


@dataclass(frozen=True)
class _State:
    symbol: sp.Symbol
    update: sp.Expr
    initial: float
    most: float | None


@dataclass(frozen=True)
class _Input:
    param: sp.Symbol
    letter: sp.Symbol
    value: float


def compile_program(problem: Problem) -> Program:
    s = symbols(problem.circuit)
    _refuse_ways(s)
    inputs = _inputs(problem, s)
    letters = {i.param: i.letter for i in inputs}
    system = equations(problem, Step(DT), letters=letters)
    if system.params:
        raise ValueNeeded(min(p.name for p in system.params))
    exprs = [_grounded(eq.expr, eq.origin, s) for eq in system.equations if eq.origin.what != "given"]
    unknowns = [u for u in system.unknowns if not is_before(u)]
    memory = _memory(relation(problem.circuit), {**parameter_values(problem, s), **letters})
    parts = _observed(s, exprs, unknowns)
    clocks = _clocks(exprs)
    junctions = _junctions(exprs, unknowns, s)
    states = memory + clocks
    params = [DT, TIME, *(st.symbol for st in states), *(i.letter for i in inputs)]
    _check_square(exprs, unknowns, params)
    index = {u: k for k, u in enumerate(unknowns)}
    return Program(
        unknowns=[u.name for u in unknowns],
        params=[p.name for p in params],
        initial=[0.0, 0.0, *(st.initial for st in states), *(i.value for i in inputs)],
        states=[(2 + k, st.most) for k, st in enumerate(states)],
        inputs={i.letter.name: 2 + len(states) + k for k, i in enumerate(inputs)},
        junctions=junctions,
        kernel_body=_kernel(exprs, unknowns, params),
        update_body=statements([(f"out[{k}]", st.update) for k, st in enumerate(states)], unknowns, params),
        nodes=_nodes(s, index),
        parts={label: {name: index[u] for name, u in named.items()} for label, named in parts.items()},
        kinds={label: e.kind.name for label, (e, _) in zip(s.labels, s.net.parts)},
        flow_body=statements(_flowing(s), unknowns, params),
        flows=_flow_places(s),
    )


def _refuse_ways(s: Symbols) -> None:
    for label, (e, _) in zip(s.labels, s.net.parts):
        if of_ways(e.kind):
            raise NotSimulated(label)


def _inputs(problem: Problem, s: Symbols) -> list[_Input]:
    """Each kind's ``inputs``, named ``<label>_<parameter>``, starting at their values."""
    values = parameter_values(problem, s)
    return [
        _Input(s.param(e, which), sp.Symbol(f"{label}_{which}"), float(values[s.param(e, which)]))
        for label, (e, _) in zip(s.labels, s.net.parts)
        for which in e.kind.inputs
    ]


def _grounded(e: sp.Expr, origin, s: Symbols) -> sp.Expr:
    """Kirchhoff's law at a point, with the point's whisper to ground."""
    return e + G_NODE * s.potentials[origin.subject] if origin.what == "kcl" else e


def _memory(rel: Relation, values) -> list[_State]:
    """What is remembered, from rest: each quantity under ``D`` or ``Pre``. An inner one only under ``Pre``
    is a state that jumps (a flip-flop's); the rest move at most so far a step."""
    under_d = {expr(a.args[0]) for eq in all_equations(rel) for a in eq.expr.atoms(D)}
    under_pre = {expr(a.args[0]) for eq in all_equations(rel) for a in eq.expr.atoms(Pre)}
    return [
        _State(before(x), subs(x, values), 0.0, None if x not in under_d and _inner(x) else _most(x))
        for x in sorted(under_d | under_pre, key=str)
    ]


def _inner(x: sp.Expr) -> bool:
    return not any(s.name.startswith(("V_", "I_")) for s in symbols_in(x))


def _most(x: sp.Expr) -> float:
    names = [s.name for s in symbols_in(x)]
    if not any(n.startswith("V_") for n in names) and any(n.startswith("I_") for n in names):
        return STEP_AMPS
    return STEP_VOLTS


def _observed(s: Symbols, exprs: list[sp.Expr], unknowns: list[sp.Symbol]) -> dict[str, dict[str, sp.Symbol]]:
    """What the page reads of each element, by name: ``U``, ``I`` of two terminals, ``I_<terminal>`` of more,
    its inner quantities, and ``PAGE``'s. A voltage not yet an unknown becomes one, with its equation."""
    out: dict[str, dict[str, sp.Symbol]] = {}
    for k, (label, (e, _)) in enumerate(zip(s.labels, s.net.parts)):
        t = s.terminals(k)
        currents = {name: c for name, c in t.I.items() if isinstance(c, sp.Symbol)}
        named: dict[str, sp.Symbol] = {}
        if len(e.kind.terminals) == 2:
            named["I"] = currents["a"] if "a" in currents else next(iter(currents.values()))
            named["U"] = _voltage(f"U_{label}", t.across(*e.kind.terminals), exprs, unknowns)
        else:
            named |= {f"I_{name}": c for name, c in currents.items()}
        named |= {name: sp.Symbol(f"{name}_{label}") for name in inner_names(e.kind)}
        for name, what in PAGE.get(e.kind.name, {}).items():
            if isinstance(what, str):
                named[name] = currents[what]
            else:
                named[name] = _voltage(f"{name[0]}_{label}{name[1:]}", t.across(*what), exprs, unknowns)
        out[label] = {name: u for name, u in named.items() if u in unknowns}
    return out


def _voltage(name: str, value: sp.Expr, exprs: list[sp.Expr], unknowns: list[sp.Symbol]) -> sp.Symbol:
    u = sp.Symbol(name)
    if u not in unknowns:
        unknowns.append(u)
        exprs.append(u - value)
    return u


def _clocks(exprs: list[sp.Expr]) -> list[_State]:
    """What time does in the data: steps short enough for each sine (``SINE_STEPS`` a period) and square
    wave (``EDGE_STEPS``), and each switch in time remembered, so a step after it starts short again."""
    limits: list[float] = []
    edges: list[sp.Expr] = []
    for e in exprs:
        for a in e.atoms(sp.sin, sp.cos):
            if TIME in a.free_symbols:
                limits.append(2 * math.pi / abs(float(sp.diff(a.args[0], TIME))) / SINE_STEPS)
        for a in e.atoms(sp.Mod):
            if TIME in a.free_symbols:
                limits.append(abs(float(a.args[1] / sp.diff(a.args[0], TIME))) / EDGE_STEPS)
        edges += [p for p in e.atoms(sp.Piecewise) if symbols_in(p) == {TIME} and p not in edges]
    states = [_State(sp.Symbol(f"edge{k}"), p, float(p.subs(TIME, 0)), None) for k, p in enumerate(edges)]
    if limits:
        states.append(_State(sp.Symbol("clock"), TIME, 0.0, min(limits)))
    return states


def _junctions(exprs: list[sp.Expr], unknowns: list[sp.Symbol], s: Symbols) -> list[tuple[int, float, float]]:
    """Each exponential of what is found becomes ``limexp`` of an unknown of its own; one of a junction is
    approached along it (its index, the scale it moves on, and where it bends)."""
    found = sorted({a for e in exprs for a in e.atoms(sp.exp) if symbols_in(a) & set(unknowns)}, key=str)
    out = []
    for k, a in enumerate(found):
        z, mark = sp.Symbol(f"exp_{k}"), sp.Dummy("e")
        marked = [e.xreplace({a: mark}) for e in exprs]
        arg = expr(a.args[0])
        bend = _bend(arg, marked, mark, unknowns, s)
        exprs[:] = [e.xreplace({mark: limexp(z)}) for e in marked]
        exprs.append(z - arg)
        unknowns.append(z)
        if bend is not None:
            out.append((len(unknowns) - 1, 1.0, bend))
    return out


def _bend(arg: sp.Expr, exprs: Sequence[sp.Expr], mark: sp.Symbol, unknowns: list[sp.Symbol], s: Symbols):
    """Where a junction's exponential bends, in its own argument (SPICE's V_crit, over n·V_T); None: not a
    junction."""
    at_zero = dict.fromkeys(unknowns, 0)
    scale = [abs(subs(sp.diff(e, mark), at_zero)) for e in exprs if e.has(mark)]
    numbers = [float(c) for c in scale if c.is_number]
    zero = subs(arg, at_zero)
    if not numbers or not zero.is_number:
        return None
    c = max(numbers)
    if c == 0 or c * math.exp(min(float(zero), 700)) >= JUNCTION:
        return None
    potentials = [p for p in s.potentials if isinstance(p, sp.Symbol)]
    slopes = [abs(float(sp.diff(arg, p))) for p in potentials if sp.diff(arg, p).is_number]
    nvt = 1 / max((x for x in slopes if x), default=1.0)
    return math.log(nvt / (math.sqrt(2) * c))


def _check_square(exprs: list[sp.Expr], unknowns: list[sp.Symbol], params: list[sp.Symbol]) -> None:
    allowed = set(unknowns) | set(params)
    stray = sorted({x for e in exprs for x in symbols_in(e)} - allowed, key=str)
    if stray:
        raise ValueNeeded(stray[0].name)
    if len(exprs) != len(unknowns):
        raise NotSimulated(f"{len(exprs)} laws, {len(unknowns)} unknowns")


def _kernel(exprs: list[sp.Expr], unknowns: list[sp.Symbol], params: list[sp.Symbol]) -> Code:
    n = len(unknowns)
    F = sp.Matrix(exprs)
    J = F.jacobian(unknowns) if n else sp.zeros(0, 0)
    targets = [(f"F[{i}]", expr(F[i])) for i in range(n)]
    targets += [(f"J[{i * n + j}]", expr(J[i, j])) for i in range(n) for j in range(n) if J[i, j] != 0]
    return statements(targets, unknowns, params)


def _nodes(s: Symbols, index: dict[sp.Symbol, int]) -> dict[str, int | None]:
    """Each point by its name (a ``Net``'s or a ``Node``'s label, else its number): its potential's index."""
    named = {n: p.name if isinstance(p, Net) else p.label for n, p in s.net.named}
    out: dict[str, int | None] = {}
    for n, v in enumerate(s.potentials):
        out[named.get(n) or str(n)] = index.get(v) if isinstance(v, sp.Symbol) else None
    return out


def _flowing(s: Symbols) -> list[tuple[str, sp.Expr]]:
    currents = [c for k, (e, _) in enumerate(s.net.parts) for c in s.currents(k).values()]
    return [(f"out[{k}]", c) for k, c in enumerate(currents)]


def _flow_places(s: Symbols) -> dict[str, list[int]]:
    out, k = {}, 0
    for label, (e, _) in zip(s.labels, s.net.parts):
        out[label] = list(range(k, k + len(e.kind.terminals)))
        k += len(e.kind.terminals)
    return out
