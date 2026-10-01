"""Circuits in time: the same laws as on paper, solved step by step in time.

A step of length ``dt`` turns every capacitor into ``I = C·(U − U_prev)/dt`` (backward
Euler) and every inductor into ``U = L·(I − I_prev)/dt``, so each step is a system of
algebraic equations — nonlinear where there are diodes and transistors. sympy writes it
down once, with its Jacobian, and turns both into code: Python here, JavaScript for the
notebook's live simulation (``Program.to_json``). Each step is then Newton's method on
plain numbers; between steps the elements' states (``Model.states``) move on.

    >>> from electro import *
    >>> trace = simulate(supply(5) + Resistor(1000) + node("A") + Capacitor(1e-3) + ground, t=5)
    >>> round(trace.at(1)["V_A"], 1)  # one time constant: 63 %
    3.2
"""

from __future__ import annotations

import cmath
import json
import math
from array import array
from dataclasses import dataclass, field

import sympy as sp
from sympy.printing.jscode import JavascriptCodePrinter
from sympy.printing.pycode import PythonCodePrinter

from . import components as comp
from .circuit import GROUND, Circuit
from .devices import BOARDS, EXP_LIMIT
from .issues import NoConvergence, NoSuchInput, NotSimulated, ValueNeeded
from .reasons import KirchhoffCurrent
from .semantics import compile_circuit
from .values import UNKNOWN

DT = sp.Symbol("dt", positive=True)
T = sp.Symbol("t", nonnegative=True)  # the time at the end of the step
G_NODE = 1e-12  # S from every node to ground: a node left floating is not a singular matrix
RELTOL, VNTOL, ABSTOL = 1e-6, 1e-6, 1e-9
MAX_NEWTON = 60


# ------------------------------------------------------------------ the program


@dataclass
class Program:
    """A circuit compiled for simulation. ``x``: unknowns, ``p``: parameters (``dt``, ``t``, the
    states, the inputs); ``kernel`` fills the residuals ``F(x, p)`` and the Jacobian ``J = ∂F/∂x`` (flat,
    row by row), ``update`` gives the states after an accepted step."""

    unknowns: list[str]
    params: list[str]
    initial: list[float]  # p at t = 0 (dt, t: placeholders, set every step)
    states: list[tuple[int, float | None]]  # param index, the most it may change in a step (None: it jumps)
    inputs: dict[str, int]  # name -> param index
    junctions: list[tuple[int, float, float]]  # unknown index, n·V_T, V_crit
    kernel_body: dict[str, str]  # "py" / "js": the kernel's statements
    update_body: dict[str, str]
    nodes: dict[str, int | None]  # node name -> index of V_<node> in x (None: the reference, 0 V)
    parts: dict[str, dict[str, int]]  # element label -> its quantities ("U", "I", ...) -> index in x
    kinds: dict[str, str]  # element label -> its class name
    # the current into each terminal of each element (for the page's moving dots): ``flow`` fills
    # ``out`` from x and p, ``flows`` says where each one is (element label -> per terminal, in its
    # order: index in out)
    flow_body: dict[str, str] = field(default_factory=lambda: {"py": "    pass", "js": ""})
    flows: dict[str, list[int]] = field(default_factory=dict)
    _kernel: object = field(default=None, repr=False)
    _update: object = field(default=None, repr=False)

    @property
    def dt_index(self) -> int:
        return 0

    def functions(self):
        if self._kernel is None:
            scope = {
                "exp": math.exp,
                "log": math.log,
                "limexp": _limexp,
                "dlimexp": _dlimexp,
                "sqrt": math.sqrt,
                "sin": math.sin,
                "cos": math.cos,
                "tanh": math.tanh,
                "floor": math.floor,
                "pi": math.pi,
                "math": math,
            }
            exec(f"def kernel(x, p, F, J):\n{self.kernel_body['py']}\n", scope)
            exec(f"def update(x, p, out):\n{self.update_body['py']}\n", scope)
            self._kernel, self._update = scope["kernel"], scope["update"]
        return self._kernel, self._update

    def to_json(self) -> str:
        """For the notebook's live simulation (``simulation/engine.ts``): the same program in JavaScript."""
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


def _limexp(x: float) -> float:
    return math.exp(x) if x <= EXP_LIMIT else math.exp(EXP_LIMIT) * (1 + x - EXP_LIMIT)


def _dlimexp(x: float) -> float:
    return math.exp(min(x, EXP_LIMIT))


class _Py(PythonCodePrinter):
    def __init__(self):
        super().__init__({"fully_qualified_modules": False, "standard": "python3"})


def _code(targets: list[tuple[str, sp.Expr]], xs: list[sp.Symbol], ps: list[sp.Symbol]) -> dict[str, str]:
    """``target = expr`` statements in Python and JavaScript, common subexpressions computed once."""
    rename = {s: sp.Symbol(f"x{i}") for i, s in enumerate(xs)} | {s: sp.Symbol(f"p{i}") for i, s in enumerate(ps)}
    exprs = [sp.sympify(e, strict=True).xreplace(rename) for _, e in targets]
    common, reduced = sp.cse(exprs, symbols=sp.numbered_symbols("t"))
    used = set().union(*(e.free_symbols for e in reduced), *(e.free_symbols for _, e in common)) if exprs else set()
    loads = [
        (s.name, f"{s.name[0]}[{s.name[1:]}]")
        for s in sorted(used, key=lambda s: s.name)
        if s.name[0] in "xp" and s.name[1:].isdigit()
    ]
    py, js = _Py(), JavascriptCodePrinter({"strict": False})
    out = {"py": [], "js": []}
    for name, source in loads:
        out["py"].append(f"    {name} = {source}")
        out["js"].append(f"const {name} = {source};")
    for s, e in common:
        out["py"].append(f"    {s} = {py.doprint(e)}")
        out["js"].append(f"const {s} = {js.doprint(e)};")
    for (target, _), e in zip(targets, reduced):
        out["py"].append(f"    {target} = {py.doprint(e)}")
        out["js"].append(f"{target} = {js.doprint(e)};")
    if not out["py"]:
        out["py"].append("    pass")
    return {"py": "\n".join(out["py"]), "js": "\n".join(out["js"])}


def compile_sim(circuit: Circuit) -> Program:
    """The circuit's laws in time, as a ``Program``: every value must be known."""
    system = compile_circuit(circuit, ctx=comp.Context(dt=DT, t=T))
    for label, placed in system.parts.items():
        c = placed.component
        if isinstance(c, comp.Hole):
            raise NotSimulated(sp.Symbol(label))
        if c.has_value and c.value is UNKNOWN and not isinstance(c, (comp.Ammeter, comp.Voltmeter)):
            raise ValueNeeded(sp.Symbol(label))

    states: dict[sp.Symbol, tuple[sp.Expr, float, float | None]] = {}
    inputs: dict[sp.Symbol, float] = {}
    junctions: list[tuple[sp.Symbol, float, float]] = []
    for placed in system.parts.values():
        states |= placed.model.states
        inputs |= placed.model.inputs
        junctions += placed.model.junctions

    known = {s: sp.Float(float(v)) for s, v in system.known.items()}
    laws = [law for law in system.laws if law.kind != "reading"]  # a meter's reading is what we find
    exprs = [law.expr for law in laws]
    unknowns = [u for u in system.unknowns if any(u in e.free_symbols for e in exprs)]
    # a tiny conductance from every node to ground: no node is ever left undetermined
    potentials = set(system.potentials.values())
    has_kcl = set()
    for i, law in enumerate(laws):
        if isinstance(law.reason, KirchhoffCurrent):
            v = system.potentials[law.reason.node.name]
            exprs[i] += G_NODE * v
            has_kcl.add(v)
    for v in unknowns:
        if v in potentials and v not in has_kcl:
            exprs.append(G_NODE * v)
    for v in system.potentials.values():
        if v not in known and v not in unknowns:
            unknowns.append(v)
            exprs.append(G_NODE * v)

    params = [DT, T, *states, *inputs]
    exprs = [e.xreplace(known) for e in exprs]
    allowed = set(unknowns) | set(params)
    for e in exprs:
        for s in e.free_symbols - allowed:
            raise ValueNeeded(s)
    if len(exprs) != len(unknowns):  # every element adds as many laws as unknowns: should not happen
        raise NotSimulated(sp.Symbol(f"{len(exprs)} laws, {len(unknowns)} unknowns"))

    n = len(unknowns)
    F = sp.Matrix(exprs)
    J = F.jacobian(unknowns)
    targets = [(f"F[{i}]", F[i]) for i in range(n)]
    targets += [(f"J[{i * n + j}]", J[i, j]) for i in range(n) for j in range(n) if J[i, j] != 0]
    kernel = _code(targets, unknowns, params)
    update = _code(
        [(f"out[{k}]", expr.xreplace(known)) for k, (expr, _, _) in enumerate(states.values())], unknowns, params
    )

    # each terminal's current, as the node's law has it (what flows from the node into the element)
    flowing: list[tuple[str, sp.Expr]] = []
    flows: dict[str, list[int]] = {}
    for label, placed in system.parts.items():
        currents = [
            sp.sympify(placed.model.inflow.get(t, 0), strict=True).xreplace(known) for t in placed.component.terminals
        ]
        if any(c.free_symbols - allowed for c in currents):
            continue  # (not all of it is known here: no dots through it)
        flows[label] = list(range(len(flowing), len(flowing) + len(currents)))
        flowing += [(f"out[{len(flowing) + k}]", c) for k, c in enumerate(currents)]
    flow = _code(flowing, unknowns, params)

    index = {u: i for i, u in enumerate(unknowns)}
    parts = {
        label: {name: index[v] for name, v in placed.model.variables.items() if v in index}
        for label, placed in system.parts.items()
    }
    return Program(
        unknowns=[u.name for u in unknowns],
        params=[p.name for p in params],
        initial=[0.0, 0.0] + [init for _, init, _ in states.values()] + list(inputs.values()),
        states=[(2 + k, most) for k, (_, _, most) in enumerate(states.values())],
        inputs={s.name: 2 + len(states) + k for k, s in enumerate(inputs)},
        junctions=[(index[u], nvt, nvt * math.log(nvt / (math.sqrt(2) * i_s))) for u, nvt, i_s in junctions],
        kernel_body=kernel,
        update_body=update,
        nodes={name: index.get(v) for name, v in system.potentials.items()},
        parts=parts,
        kinds={label: type(placed.component).__name__ for label, placed in system.parts.items()},
        flow_body=flow,
        flows=flows,
    )


# ------------------------------------------------------------------ the numbers


def _solve_linear(A: list[float], b: list[float], n: int) -> list[float] | None:
    """``A·x = b`` (``A`` flat, row by row) by Gaussian elimination with partial pivoting."""
    M = []
    for i in range(n):  # each row scaled to its largest entry: laws in volts and in amperes pivot alike
        row = A[i * n : (i + 1) * n] + [b[i]]
        big = max(abs(v) for v in row[:n]) or 1.0
        M.append([v / big for v in row])
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(M[r][col]))
        if abs(M[pivot][col]) < 1e-300:
            return None
        M[col], M[pivot] = M[pivot], M[col]
        row = M[col]
        inv = 1.0 / row[col]
        for r in range(col + 1, n):
            f = M[r][col] * inv
            if f:
                Mr = M[r]
                for c in range(col, n + 1):
                    Mr[c] -= f * row[c]
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        s = M[i][n] - sum(M[i][j] * x[j] for j in range(i + 1, n))
        x[i] = s / M[i][i]
    return x


def _pnjlim(new: float, old: float, nvt: float, vcrit: float) -> float:
    """SPICE's junction voltage limiting: along the exponential, never far past it in one go."""
    if new > vcrit and abs(new - old) > 2 * nvt:
        if old > 0:
            arg = 1 + (new - old) / nvt
            return old + nvt * math.log(arg) if arg > 0 else vcrit
        return nvt * math.log(new / nvt)
    return new


class Simulation:
    """A program running: ``advance(dt)`` one step at a time, or ``run_until(t)``."""

    def __init__(self, program: Program):
        self.program = program
        self.kernel, self.update = program.functions()
        self.n = len(program.unknowns)
        self.x = [0.0] * self.n
        self.p = list(program.initial)
        self.t = 0.0
        self.switched = False  # a flip-flop changed in the last step
        self.step = 0.0  # the next step's length

    def set_input(self, name: str, value: float) -> None:
        self.p[self.program.inputs[name]] = float(value)

    def newton(self, dt: float) -> tuple[list[float], int] | None:
        n, p = self.n, self.p
        p[0], p[1] = dt, self.t + dt
        x = list(self.x)
        F, J = [0.0] * n, [0.0] * (n * n)
        for iteration in range(1, MAX_NEWTON + 1):
            for k in range(n * n):
                J[k] = 0.0
            self.kernel(x, p, F, J)
            dx = _solve_linear(J, [-f for f in F], n)
            if dx is None or any(math.isnan(d) for d in dx):
                return None
            new = [a + d for a, d in zip(x, dx)]
            for i, nvt, vcrit in self.program.junctions:
                new[i] = _pnjlim(new[i], x[i], nvt, vcrit)
            done = all(abs(a - b) <= RELTOL * max(abs(a), abs(b)) + VNTOL for a, b in zip(new, x))
            x = new
            if done and iteration > 1:
                return x, iteration
        return None

    def advance_to(self, target: float, dt_max: float, schedule=None, on_step=None) -> None:
        """Steps up to ``target``: as long as each state allows (``Model.states``), at most ``dt_max``;
        shorter after a flip-flop switched, or when Newton's method did not converge. A state that
        still moves too far in the shortest step jumps for real (a capacitor put across an ideal
        source): that step is taken."""
        dt_min = dt_max * 1e-9
        self.step = min(self.step or min(dt_max, 1e-6), dt_max)
        while self.t < target - 1e-15:
            h = min(self.step, target - self.t)
            if schedule is not None:
                for i, value in schedule(self.t):
                    self.p[i] = value
            ok, change = self.advance(h, jump=h <= dt_min)
            if not ok:
                if h <= dt_min:
                    raise NoConvergence(self.t)
                self.step = h / 4 if change == math.inf else h / 2
                continue
            if on_step is not None:
                on_step()
            if self.switched:
                self.step = max(dt_min, h / 8)
            elif change < 0.25 and h >= self.step * 0.999:
                self.step = min(dt_max, h * 2)

    def run(self, t_end: float, dt_max: float, schedule=None, on_step=None) -> None:
        """From rest to ``t_end``; ``on_step`` also at t = 0, with the state after a first tiny step
        (the circuit the instant it starts)."""
        if schedule is not None:
            for i, value in schedule(0.0):
                self.p[i] = value
        self.advance_to(min(1e-9, t_end), dt_max, schedule)
        self.t = 0.0
        if on_step is not None:
            on_step()
        self.advance_to(t_end, dt_max, schedule, on_step)

    def advance(self, dt: float, jump: bool = False) -> tuple[bool, float]:
        """Try one step of ``dt``: (accepted?, how much of its allowed change a state used);
        ``jump``: taken whatever the change, as long as Newton's method converged."""
        found = self.newton(dt)
        if found is None:
            return False, math.inf
        x, _ = found
        after = [0.0] * len(self.program.states)
        self.update(x, self.p, after)
        change = 0.0
        for (i, most), value in zip(self.program.states, after):
            if most is not None:
                change = max(change, abs(value - self.p[i]) / most)
        if change > 1 and not jump:
            return False, change
        self.x, self.t = x, self.t + dt
        self.switched = False
        for (i, most), value in zip(self.program.states, after):
            if most is None and value != self.p[i]:
                self.switched = True
            self.p[i] = value
        return True, change


# ------------------------------------------------------------------ simulate()


def _resample(t: list[float], y: list[float], at: list[float]) -> list[float]:
    """``y(t)`` at the times ``at`` (increasing), by straight lines between the steps."""
    out, i = [], 0
    for s in at:
        while i + 1 < len(t) - 1 and t[i + 1] <= s:
            i += 1
        t0, t1 = t[i], t[min(i + 1, len(t) - 1)]
        f = 0.0 if t1 == t0 else min(max((s - t0) / (t1 - t0), 0.0), 1.0)
        out.append(y[i] + f * (y[min(i + 1, len(t) - 1)] - y[i]))
    return out


def _fft(x: list[float]) -> list[complex]:
    """Radix-2 FFT (``len(x)`` a power of two), iterative: no numpy in the notebook."""
    n = len(x)
    a = [complex(v) for v in x]
    j = 0
    for i in range(1, n):  # bit-reversed order
        bit = n >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j |= bit
        if i < j:
            a[i], a[j] = a[j], a[i]
    size = 2
    while size <= n:
        w = cmath.exp(-2j * math.pi / size)
        for start in range(0, n, size):
            wk = 1
            for k in range(size // 2):
                u, v = a[start + k], a[start + k + size // 2] * wk
                a[start + k], a[start + k + size // 2] = u + v, u - v
                wk *= w
        size <<= 1
    return a


@dataclass
class Trace:
    """What happened: ``t`` and every quantity's value at each accepted step."""

    names: list[str]
    t: list[float]
    # every step's values one after another (len(names) a step), 8 bytes a number: a long run
    # of a big circuit would take several times more as lists of floats (and Pyodide's memory
    # never shrinks back)
    data: array
    program: Program

    def __getitem__(self, name: str) -> list[float]:
        return self.data[self._column(name) :: len(self.names)].tolist()

    def _column(self, name: str) -> int:
        if name in self.names:
            return self.names.index(name)
        loose = name.replace("_", "")
        for i, n in enumerate(self.names):
            if n.replace("_", "") == loose:
                return i
        from .issues import NoSuchQuantity

        raise NoSuchQuantity(name, [sp.Symbol(n) for n in self.names])

    def at(self, t: float) -> dict[str, float]:
        """Every quantity at time ``t`` (the last step not after it)."""
        k = max((i for i, s in enumerate(self.t) if s <= t + 1e-15), default=0)
        n = len(self.names)
        return dict(zip(self.names, self.data[k * n : (k + 1) * n]))

    def V(self, node: str) -> list[float]:
        return self[f"V_{node}"]

    def U(self, label: str) -> list[float]:
        return self[f"U_{label}"]

    def I(self, label: str) -> list[float]:  # noqa: E743 — the name physics uses
        return self[f"I_{label}"]

    def plot(self, *names: str):
        from .plot import TracePlot

        return TracePlot(self, list(names) or self.default_signals())

    def spectrum(self, *names: str, points: int = 4096, f_max: float | None = None):
        """Each quantity's amplitude at each frequency (FFT of the trace resampled evenly, Hann
        window): a sine of 5 V at 50 Hz is a peak of 5 at 50. Up to ``f_max`` Hz (by default a
        quarter of the sampling rate). Plots like a sweep, over f."""
        from .analysis import Sweep

        names = names or tuple(self.default_signals())
        t0, t1 = self.t[0], self.t[-1]
        n = 1 << max(3, (points - 1).bit_length())  # a power of two
        dt = (t1 - t0) / n
        window = [0.5 - 0.5 * math.cos(2 * math.pi * k / n) for k in range(n)]
        gain = 2 / sum(window)
        keep = n // 4 if f_max is None else min(n // 2, int(f_max * dt * n) + 1)
        values = {}
        for name in names:
            samples = _resample(self.t, self[name], [t0 + k * dt for k in range(n)])
            mean = sum(samples) / n
            spectrum = _fft([(v - mean) * w for v, w in zip(samples, window)])
            values[name] = [abs(mean)] + [abs(x) * gain for x in spectrum[1:keep]]
        return Sweep("f", "Hz", [k / (dt * n) for k in range(keep)], values)

    def default_signals(self) -> list[str]:
        """Capacitors' voltages, LEDs' currents and named nodes (at most four); else every node."""
        named = [
            f"V_{n}"
            for n, i in self.program.nodes.items()
            if i is not None and n != GROUND and not (n[0] == "n" and n[1:].isdigit())
        ]
        caps = [f"U_{label}" for label, kind in self.program.kinds.items() if kind == "Capacitor"]
        leds = [f"I_{label}" for label, kind in self.program.kinds.items() if kind == "LED"]
        chosen = caps + leds + named
        if not chosen:
            chosen = [f"V_{n}" for n, i in self.program.nodes.items() if i is not None]
        return chosen[:4]

    def _repr_svg_(self):
        return self.plot()._repr_svg_()


INPUTS = ("closed", "position", "lux", "temperature")  # an element's input, <label>_<this>: named by its label alone


def _input_values(program: Program, name: str):
    """``name`` → a function from its value to ``[(param index, number)]``: a number, or for an
    board's pin (``ARD_1.D13``, ``PICO_1.GP15``) one of its modes ("high", "low", "input", "pullup", …)."""
    if "." in name:
        label, pin = name.split(".", 1)
        G, E = f"{label}_{pin}_G", f"{label}_{pin}_E"
        board = BOARDS.get(program.kinds.get(label, ""))
        if G in program.inputs and board is not None and pin in board.PINS:
            modes = board.MODES

            def pin_mode(mode):
                g, e = modes[mode] if isinstance(mode, str) else (modes["high"][0], float(mode))
                return [(program.inputs[G], g), (program.inputs[E], e)]

            return pin_mode
    for candidate in (name, *(f"{name}_{suffix}" for suffix in INPUTS)):
        if candidate in program.inputs:
            return lambda value, i=program.inputs[candidate]: [(i, float(value))]
    available = [
        n.rsplit("_", 1)[0] if n.endswith(INPUTS) else n for n in program.inputs if not n.endswith(("_G", "_E"))
    ]
    available += sorted({f"{n.rsplit('_', 2)[0]}.{n.rsplit('_', 2)[1]}" for n in program.inputs if n.endswith("_G")})
    raise NoSuchInput(name, available)


def _schedule(program: Program, inputs: dict | None):
    """The inputs as one function of time: ``t → [(param index, number)]`` (None: no inputs)."""
    if not inputs:
        return None
    parts = [(_input_values(program, name), value) for name, value in inputs.items()]
    return lambda now: [
        pair for to_values, value in parts for pair in to_values(value(now) if callable(value) else value)
    ]


def _run_python(program: Program, t_end: float, dt_max: float, schedule) -> tuple[list[float], array]:
    sim = Simulation(program)
    times, rows = [], array("d")

    def record():
        times.append(sim.t)
        rows.extend(sim.x)

    sim.run(t_end, dt_max, schedule, record)
    return times, rows


def _run_javascript(engine, program: Program, t_end: float, dt_max: float, schedule):
    """In the notebook (Pyodide): the same loop in the page's engine (``simulation/engine.ts``), JIT-compiled."""
    from pyodide.ffi import create_proxy

    callback = create_proxy(lambda now: [list(pair) for pair in schedule(now)]) if schedule else None
    try:
        result = engine.run(program.to_json(), t_end, dt_max, callback)
    except Exception as err:  # the engine's NoConvergence comes as a JS error with the time in it
        text = str(err)
        if "NoConvergence" in text:
            raise NoConvergence(float(text.rsplit(" ", 1)[-1])) from None
        raise
    finally:
        if callback is not None:
            callback.destroy()
    times, rows = array("d"), array("d")
    times.frombytes(result.t.to_bytes())
    rows.frombytes(result.rows.to_bytes())  # straight from the engine's Float64Array, no float by float
    return times.tolist(), rows


def _engine():
    import sys

    if sys.platform != "emscripten":
        return None
    import js

    return getattr(js, "electroSim", None)


def simulate(circuit: Circuit, t: float = 1.0, *, dt: float | None = None, inputs: dict | None = None) -> Trace:
    """The circuit from rest (every capacitor empty) for ``t`` seconds.

    ``dt``: the longest step (default ``t``/500; steps shrink by themselves where things
    change fast). ``inputs``: switches (``{"S_1": 1}``), potentiometers (``{"P_1": 0.3}``),
    light on a photoresistor in lux, a thermistor's temperature in °C, or a board's pins (``{"ARD_1.D13": "high"}``), each a value or a function of time.
    """
    program = compile_sim(circuit)
    schedule = _schedule(program, inputs)
    dt_max = dt or t / 500
    engine = _engine()
    times, rows = (
        _run_javascript(engine, program, t, dt_max, schedule)
        if engine is not None
        else _run_python(program, t, dt_max, schedule)
    )
    return Trace(program.unknowns, times, rows, program)
