"""Black-boxing: what a circuit looks like from its terminals.

``blackbox(c)`` is the semantic functor proper: it sends a circuit ``m → n`` to the
(affine) relation between its boundary potentials and currents, with every internal
variable eliminated. Two circuits are equivalent iff their black boxes are equal.
"""

from __future__ import annotations

import cmath
import math
from dataclasses import dataclass

import sympy as sp

from .circuit import Circuit, Close, Seq, ground
from .components import Context, CurrentSource, VoltageSource
from .devices import SineSource
from .issues import NotAPort, NoThevenin, NotLinear
from .semantics import compile_circuit
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
    except sp.solvers.solveset.NonlinearError as err:
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
    """Frequency response ``H(jω) = output / input``: the expression in ``omega`` and its samples."""

    H: sp.Expr
    output: str
    input: str | None
    f: list[float]
    values: list[complex]

    @property
    def gain_db(self) -> list[float]:
        return [20 * math.log10(max(abs(h), 1e-300)) for h in self.values]

    @property
    def phase_deg(self) -> list[float]:
        """Unwrapped: no jumps of 360° where the phase passes −180°."""
        out: list[float] = []
        for h in self.values:
            p = math.degrees(cmath.phase(h))
            if out:
                p += 360 * round((out[-1] - p) / 360)
            out.append(p)
        return out

    def __repr__(self):
        return f"H(jω) = {self.H}"

    def _repr_svg_(self) -> str:
        from .plot import BodePlot

        return BodePlot(self)._repr_svg_()


def bode(c: Circuit, output: str, input: str | None = None, *, f=(10, 1e6), points: int = 200) -> Response:
    """The frequency response of ``output`` (``"V_A"``, ``"I_R_1"``) from ``f[0]`` to ``f[1]`` Hz, per
    ``input`` (a quantity's name; by default the only voltage source's value, if there is one).

    Solved once with a symbolic ``omega``, then only evaluated at each frequency.
    """
    sol = solve(c, omega=OMEGA)
    H = sol(output)
    if input is None:
        sources = [p for p in sol.system.parts.values() if isinstance(p.component, (VoltageSource, SineSource))]
        if len(sources) == 1:
            input = sources[0].model.param.name
    if input is not None:
        H = sp.simplify(H / sol(input))
    at = sp.lambdify(OMEGA, H, "math")
    lo, hi = math.log10(f[0]), math.log10(f[1])
    freqs = [10 ** (lo + (hi - lo) * k / (points - 1)) for k in range(points)]
    return Response(H, output, input, freqs, [complex(at(2 * math.pi * x)) for x in freqs])
