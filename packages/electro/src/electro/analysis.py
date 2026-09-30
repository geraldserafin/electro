"""Black-boxing: what a circuit looks like from its terminals.

``blackbox(c)`` is the semantic functor proper: it sends a circuit ``m → n`` to the
(affine) relation between its boundary potentials and currents, with every internal
variable eliminated. Two circuits are equivalent iff their black boxes are equal.
"""

from __future__ import annotations

import cmath
import math
import re
from dataclasses import dataclass, field
from functools import cached_property

import sympy as sp
from sympy.solvers.solveset import NonlinearError

from .circuit import GROUND, Circuit, Close, Seq, ground
from .components import Capacitor, Context, CurrentSource, Inductor, Resistor, VoltageSource
from .devices import SineSource
from .issues import NotAPort, NoThevenin, NotLinear
from .numeric import LinearSystem
from .semantics import compile_circuit, structure
from .solver import solve
from .values import fmt, parse


@dataclass(frozen=True)
class Relation:
    """Linear relation ``A·x = b`` over boundary variables ``x``, in reduced row echelon form."""

    variables: tuple[sp.Symbol, ...]
    A: sp.Matrix
    b: sp.Matrix
    empty: bool = False  # no state satisfies the laws

    def __eq__(self, other):
        if not isinstance(other, Relation):
            return NotImplemented
        if self.empty or other.empty:
            return self.empty == other.empty and len(self.variables) == len(other.variables)
        return (
            [s.name for s in self.variables] == [s.name for s in other.variables]
            and self.A.shape == other.A.shape
            and sp.simplify(self.A - other.A).is_zero_matrix
            and sp.simplify(self.b - other.b).is_zero_matrix
        )

    __hash__ = None

    def equations(self) -> list[sp.Equality]:
        x = sp.Matrix(self.variables)
        return [sp.Eq((self.A[i, :] * x)[0], self.b[i]) for i in range(self.A.rows)]

    def __repr__(self):
        if self.empty:
            return "Relation(∅)"
        return "\n".join(str(e).replace("Eq(", "").rstrip(")").replace(", ", " = ") for e in self.equations())


def blackbox(c: Circuit, *, omega=None) -> Relation:
    ctx = Context(None if omega is None else parse(omega))
    system = compile_circuit(c, ctx=ctx, open_boundary=True, unknowns_as_symbols=True)
    exprs = [law.expr.xreplace(system.known) for law in system.laws if law.kind != "reading"]
    internal = [u for u in system.unknowns if u not in system.boundary]
    variables = internal + system.boundary
    try:
        A, b = sp.linear_eq_to_matrix(exprs, variables)
    except NonlinearError as err:
        raise NotLinear() from err
    reduced, pivots = A.row_join(b).rref(simplify=True)
    k, n = len(internal), len(variables)
    if n in pivots:
        return Relation(tuple(system.boundary), sp.zeros(0, n - k), sp.zeros(0, 1), empty=True)
    rows = [i for i, p in enumerate(pivots) if p >= k]
    return Relation(
        tuple(system.boundary),
        sp.Matrix([list(reduced[i, k:n]) for i in rows]) if rows else sp.zeros(0, n - k),
        sp.Matrix([reduced[i, n] for i in rows]) if rows else sp.zeros(0, 1),
    )


@dataclass(frozen=True)
class Thevenin:
    """Two-terminal equivalent: ``U = E + Z·I`` (current entering on the left terminal)."""

    E: sp.Expr
    Z: sp.Expr

    def __repr__(self):
        unit = "Ω" if not sp.sympify(self.Z).has(sp.I) else "Ω (Z)"
        return f"E_th = {fmt(self.E, 'V')}, R_th = {fmt(self.Z, unit)}"


def equivalent(c: Circuit, *, omega=None) -> Thevenin:
    """Thévenin equivalent seen between the two terminals of a 1 → 1 circuit, or between
    the output of a 0 → 1 circuit and ground."""
    t = sp.Symbol("I_t")
    probe = CurrentSource(t, label="TEST")
    if (c.dom, c.cod) == (1, 1):
        closed = Close(Seq((c, probe)))
    elif (c.dom, c.cod) == (0, 1):
        closed = Seq((c, probe.transpose(), ground))
    else:
        raise NotAPort(str(c.type))
    ctx = Context(None if omega is None else parse(omega))
    system = compile_circuit(closed, ctx=ctx, unknowns_as_symbols=True)
    exprs = [law.expr.xreplace(system.known) for law in system.laws if law.kind != "reading"]
    solutions = sp.solve(exprs, system.unknowns, dict=True)
    u = system.parts["TEST"].model.variables["U"]
    if not solutions or u not in solutions[0]:
        raise NoThevenin()
    voltage = sp.expand(solutions[0][u])
    return Thevenin(sp.simplify(voltage.subs(t, 0)), sp.simplify(sp.diff(voltage, t)))


def resistance(c: Circuit, *, omega=None) -> sp.Expr:
    """Equivalent resistance (impedance for ``omega``) of a 1 → 1 circuit."""
    return equivalent(c, omega=omega).Z


OMEGA = sp.Symbol("omega", positive=True)


@dataclass(frozen=True)
class Response:
    """Frequency responses ``H(jω) = output / input``: each output's samples, and on asking
    (``H``) its expression in ``omega`` — solved on paper, slow for a big circuit."""

    input: str | None
    f: list[float]
    values: dict[str, list[complex]]
    circuit: Circuit = field(repr=False, compare=False)

    @cached_property
    def H(self) -> dict[str, sp.Expr]:
        sol = solve(self.circuit, omega=OMEGA)
        return {n: sol(n) if self.input is None else sp.simplify(sol(n) / sol(self.input)) for n in self.values}

    @property
    def gain_db(self) -> dict[str, list[float]]:
        return {n: [20 * math.log10(max(abs(h), 1e-300)) for h in hs] for n, hs in self.values.items()}

    @property
    def phase_deg(self) -> dict[str, list[float]]:
        """Unwrapped: no jumps of 360° where the phase passes −180°."""
        out: dict[str, list[float]] = {}
        for n, hs in self.values.items():
            out[n] = []
            for h in hs:
                p = math.degrees(cmath.phase(h))
                if out[n]:
                    p += 360 * round((out[n][-1] - p) / 360)
                out[n].append(p)
        return out

    def cutoffs(self, name: str | None = None) -> list[float]:
        """Where ``name``'s gain (by default the first output's) is 3 dB below its peak, in Hz: a
        low-pass filter's corner, a band-pass filter's two edges. Between samples, on the log scale."""
        gain = self.gain_db[name or next(iter(self.values))]
        edge = max(gain) - 3.0103  # half the power
        out = []
        for k in range(1, len(gain)):
            a, b = gain[k - 1] - edge, gain[k] - edge
            if a * b < 0:
                t = a / (a - b)
                out.append(10 ** (math.log10(self.f[k - 1]) + t * (math.log10(self.f[k]) - math.log10(self.f[k - 1]))))
        return out

    def __repr__(self):
        return "\n".join(f"{n}: H(jω) = {h}" for n, h in self.H.items())

    def _repr_svg_(self) -> str:
        from .plot import BodePlot

        return BodePlot(self)._repr_svg_()


def _outputs(system) -> list[str]:
    """Named nodes' potentials (``V_A``), or else every capacitor's and inductor's voltage."""
    named = [f"V_{n}" for n in system.potentials if n != GROUND and not re.fullmatch(r"(.+_)?n\d+", n)]
    return named or [f"U_{p.label}" for p in system.parts.values() if isinstance(p.component, (Capacitor, Inductor))]


def _source(system) -> str | None:
    """The only voltage source's value (``E_1``), if there is just one."""
    sources = [p for p in system.parts.values() if isinstance(p.component, (VoltageSource, SineSource))]
    return sources[0].model.param.name if len(sources) == 1 else None


def bode(c: Circuit, *outputs: str, input: str | None = None, f=(10, 1e6), points: int = 200) -> Response:
    """The frequency response of each of ``outputs`` (``"V_A"``, ``"I_R_1"``; by default the named
    nodes that depend on it, else the capacitors' and inductors' voltages) from ``f[0]`` to ``f[1]`` Hz,
    per ``input`` (a quantity's name; by default the only voltage source's value, if there is one).

    Compiled once with a symbolic ``omega``, then solved in numbers at each frequency.
    """
    ls = LinearSystem(c, Context(OMEGA), (OMEGA,))
    given = bool(outputs)
    outputs = outputs or tuple(_outputs(ls.system))
    if not outputs:
        raise ValueError("bode(): no output — name a node or pass one, e.g. bode(c, 'V_A')")
    input = input or _source(ls.system)
    lo, hi = math.log10(f[0]), math.log10(f[1])
    freqs = [10 ** (lo + (hi - lo) * k / (points - 1)) for k in range(points)]
    values: dict[str, list[complex]] = {n: [] for n in outputs}
    for x in freqs:
        w = (2 * math.pi * x,)
        solution = ls.solve(*w)
        ref = ls.value(input, solution, w) if input else 1
        for n in outputs:
            values[n].append(ls.value(n, solution, w) / ref)
    if not given:  # of the outputs picked here, not those the same at every frequency (the input's own node)
        varies = {n: v for n, v in values.items() if max(abs(h - v[0]) for h in v) > 1e-9 * (abs(v[0]) + 1e-12)}
        values = varies or values
    return Response(input, freqs, values, c)


@dataclass(frozen=True)
class Sweep:
    """Outputs as one element's value (``x_name``) goes through ``t``: a plot like a trace's, over
    that value instead of time. With ``omega``, each output's amplitude."""

    x_name: str
    x_unit: str
    t: list[float]
    values: dict[str, list[float]]

    def __getitem__(self, name: str) -> list[float]:
        return self.values[name]

    def __repr__(self):
        return f"Sweep({self.x_name}: {fmt(self.t[0], self.x_unit)} … {fmt(self.t[-1], self.x_unit)}; {', '.join(self.values)})"

    def _repr_svg_(self) -> str:
        from .plot import TracePlot

        return TracePlot(self, list(self.values))._repr_svg_()


def sweep(c: Circuit, element: str, values, *outputs: str, omega=None, points: int = 100) -> Sweep:
    """``outputs`` (by default the named nodes, else the element's own ``U`` and ``I``) as the value
    of ``element`` (``"R_2"``, ``"R2"``) goes through ``values``: a list, or ``(lo, hi)`` in ``points``
    even steps. At a frequency ``omega`` (rad/s), their amplitudes.

    Compiled once with the value as a symbol, then solved in numbers at each point.
    """
    placed = structure(c).part(element)
    param = placed.model.param
    if param is None:
        raise ValueError(f"sweep(): {element} has no value to change")
    ctx = Context(None if omega is None else parse(omega))
    ls = LinearSystem(c, ctx, (param,))
    outputs = outputs or tuple(
        [n for n in _outputs(ls.system) if n.startswith("V_")] or (f"U_{placed.label}", f"I_{placed.label}")
    )
    if isinstance(values, tuple) and len(values) == 2:
        lo, hi = (float(parse(v)) for v in values)
        values = [lo + (hi - lo) * k / (points - 1) for k in range(points)]
    values = [float(parse(v)) for v in values]
    out: dict[str, list[float]] = {n: [] for n in outputs}
    for v in values:
        x = ls.solve(v)
        for n in outputs:
            y = ls.value(n, x, (v,))
            out[n].append(abs(y) if omega is not None else y.real)
    return Sweep(placed.label, placed.component.unit, values, out)


@dataclass(frozen=True)
class Spread:
    """Outputs over many builds of the circuit, each part somewhere in its tolerance: their values
    run by run (``values``), and what that makes of them (``stats``)."""

    values: dict[str, list[float]]
    tol: dict[str, float]

    def stats(self, name: str) -> dict[str, float]:
        v = sorted(self.values[name])
        n = len(v)
        mean = sum(v) / n
        return {
            "mean": mean,
            "std": math.sqrt(sum((x - mean) ** 2 for x in v) / max(1, n - 1)),
            "min": v[0],
            "max": v[-1],
            "p1": v[int(0.01 * (n - 1))],
            "p99": v[int(0.99 * (n - 1))],
        }

    def __repr__(self):
        rows = []
        for n in self.values:
            s = self.stats(n)
            rows.append(f"{n}: {s['mean']:.4g} ± {s['std']:.2g} (od {s['min']:.4g} do {s['max']:.4g})")
        return "\n".join(rows)

    def _repr_svg_(self) -> str:
        from .plot import HistogramPlot

        return HistogramPlot(self)._repr_svg_()


def tolerance(c: Circuit, *outputs: str, tol=0.05, runs: int = 500, omega=None, seed: int = 0) -> Spread:
    """``outputs`` (by default the named nodes, else the voltages across the first four parts that
    vary) when every resistor, capacitor and inductor is
    anywhere within its tolerance (uniformly): ``tol`` for all, or by kind, ``{"R": 0.01, "C": 0.2}``.
    At a frequency ``omega``, amplitudes. The same ``seed``, the same builds."""
    import random

    ctx = Context(None if omega is None else parse(omega))
    shape = structure(c)
    kinds = {comp.prefix: comp for comp in (Resistor, Capacitor, Inductor)}
    varied = []
    for p in shape.parts.values():
        kind = type(p.component)
        if kind in kinds.values() and p.model.param is not None:
            t = tol if not isinstance(tol, dict) else tol.get(kind.prefix, 0)
            if t:
                varied.append((p.model.param, float(p.component.value), float(t)))
    ls = LinearSystem(c, ctx, tuple(s for s, _, _ in varied))
    # by default the named nodes, else the voltages across the parts that vary (the first four)
    labels = {p.model.param: p.label for p in shape.parts.values()}
    outputs = outputs or tuple(n for n in _outputs(ls.system) if n.startswith("V_"))
    outputs = outputs or tuple(f"U_{labels[s]}" for s, _, _ in varied[:4])
    if not outputs:
        raise ValueError("tolerance(): nothing varies and nothing is named — give it an output, e.g. 'V_A'")
    rng = random.Random(seed)
    values: dict[str, list[float]] = {n: [] for n in outputs}
    for _ in range(runs):
        point = tuple(v * (1 + rng.uniform(-t, t)) for _, v, t in varied)
        x = ls.solve(*point)
        for n in outputs:
            y = ls.value(n, x, point)
            values[n].append(abs(y) if omega is not None else y.real)
    return Spread(values, {str(s): t for s, _, t in varied})
