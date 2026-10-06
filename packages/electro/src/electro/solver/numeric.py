"""Numbers, where algebra stops (a diode's exp): equations compiled once into code that fills their residuals
and Jacobian — Python here, JavaScript for the page's engine — and Newton's method on it. The same for a
circuit at rest (``solve``) and for each step of one in time (``simulate``).

Two things help Newton, both read off the shape of the laws, never any element's: every exponential grows
along its tangent far out, and one that is tiny at zero but steep (as a p-n junction's, whatever has one) is
approached along it, as SPICE does.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import cast

import sympy as sp
from sympy.printing.jscode import JavascriptCodePrinter
from sympy.printing.pycode import PythonCodePrinter

from .expressions import expr, subs, symbols_in

Code = dict[str, str]
"""``"py"`` and ``"js"``: the same statements in each."""

Kernel = Callable[[list[float], list[float], list[float], list[float]], None]
"""``(x, p, F, J)``: fills ``F`` with the equations' values at the unknowns ``x`` and parameters ``p``, ``J``
(zeroed first) with their derivatives, n × n row by row."""

EXP_LIMIT = 80.0
JUNCTION = 1e-6
"""An exponential less than this at zero is approached along it."""
RELTOL, VNTOL = 1e-6, 1e-6
MAX_NEWTON = 60


@dataclass
class Compiled:
    """Equations as code over ``unknowns`` and ``params``. ``junctions``: each junction's unknown, the scale
    it moves on and where it bends."""

    unknowns: list[sp.Symbol]
    params: list[sp.Symbol]
    kernel_body: Code
    junctions: list[tuple[int, float, float]]
    _kernel: Kernel | None = field(default=None, repr=False)

    @property
    def kernel(self) -> Kernel:
        if self._kernel is None:
            self._kernel = cast(Kernel, python(f"def kernel(x, p, F, J):\n{self.kernel_body['py']}\n")["kernel"])
        return self._kernel

    def newton(self, x0: Sequence[float], p: Sequence[float]) -> list[float] | None:
        return newton(self.kernel, x0, p, self.junctions)


def compile_equations(
    exprs: Sequence[sp.Expr],
    unknowns: Sequence[sp.Symbol],
    params: Sequence[sp.Symbol],
    potentials: Sequence[sp.Expr],
    limited: bool = True,
) -> Compiled:
    """``exprs`` = 0 as code; ``potentials``: the points', to tell a junction's scale. ``limited``: every
    exponential continued by its tangent far out (a model that runs); else exactly the law."""
    exprs, unknowns = list(exprs), list(unknowns)
    junctions = _junctions(exprs, unknowns, potentials, limexp if limited else sp.exp)
    n = len(unknowns)
    F = sp.Matrix(exprs)
    J = F.jacobian(unknowns) if n else sp.zeros(0, 0)
    targets = [(f"F[{i}]", expr(F[i])) for i in range(n)]
    targets += [(f"J[{i * n + j}]", expr(J[i, j])) for i in range(n) for j in range(n) if J[i, j] != 0]
    return Compiled(unknowns, list(params), statements(targets, unknowns, params), junctions)


def newton(kernel: Kernel, x0: Sequence[float], p: Sequence[float], junctions=()) -> list[float] | None:
    """A root near ``x0``, or None. The same as the page's engine (``simulation/engine.ts``)."""
    n = len(x0)
    x, F, J = list(x0), [0.0] * n, [0.0] * (n * n)
    p = list(p)
    for iteration in range(1, MAX_NEWTON + 1):
        J[:] = [0.0] * (n * n)
        try:
            kernel(x, p, F, J)
        except OverflowError:
            return None
        dx = solve_linear(J, [-f for f in F], n)
        if dx is None or any(math.isnan(d) for d in dx):
            return None
        new = [a + d for a, d in zip(x, dx)]
        for i, nvt, vcrit in junctions:
            new[i] = junction_step(new[i], x[i], nvt, vcrit)
        done = all(abs(a - b) <= RELTOL * max(abs(a), abs(b)) + VNTOL for a, b in zip(new, x))
        x = new
        if done and iteration > 1:
            return x
    return None


def homotopy(find: Callable[[Sequence[float], float], list[float] | None], n: int) -> list[float] | None:
    """A root at λ = 1 of what ``find(x0, λ)`` finds near ``x0``, the sources raised from λ = 0, where
    everything is zero. Each raise starts where the last ended; a raise Newton does not finish is halved."""
    x = find([0.0] * n, 0.0)
    lam, raise_by = 0.0, 0.25
    while x is not None and lam < 1:
        to = min(1.0, lam + raise_by)
        found = find(x, to)
        if found is None:
            raise_by /= 2
            if raise_by < 1e-6:
                return None
            continue
        x, lam, raise_by = found, to, min(1.0, raise_by * 2)
    return x


def junction_step(new: float, old: float, nvt: float, vcrit: float) -> float:
    """SPICE's: along the exponential, never far past its bend in one go."""
    if new > vcrit and abs(new - old) > 2 * nvt:
        if old > 0:
            arg = 1 + (new - old) / nvt
            return old + nvt * math.log(arg) if arg > 0 else vcrit
        return nvt * math.log(new / nvt)
    return new


def solve_linear(A: list[float], b: list[float], n: int) -> list[float] | None:
    """``A·x = b`` (``A`` flat, row by row) by Gaussian elimination with partial pivoting; each row scaled
    to its largest entry first, so laws in volts and in amperes pivot alike. None: singular."""
    M = [_scaled(A[i * n : (i + 1) * n] + [b[i]], n) for i in range(n)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(M[r][col]))
        if abs(M[pivot][col]) < 1e-300:
            return None
        M[col], M[pivot] = M[pivot], M[col]
        _eliminate_below(M, col, n)
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        x[i] = (M[i][n] - sum(M[i][j] * x[j] for j in range(i + 1, n))) / M[i][i]
    return x


def _scaled(row: list[float], n: int) -> list[float]:
    big = max(abs(v) for v in row[:n]) or 1.0
    return [v / big for v in row]


def _eliminate_below(M: list[list[float]], col: int, n: int) -> None:
    row = M[col]
    inv = 1.0 / row[col]
    for r in range(col + 1, n):
        f = M[r][col] * inv
        if f:
            Mr = M[r]
            for c in range(col, n + 1):
                Mr[c] -= f * row[c]


def python(source: str) -> dict:
    """``source`` (made by ``statements``) run: what it defines, with the functions it calls."""
    scope = {
        "exp": math.exp,
        "limexp": limited_exp,
        "dlimexp": limited_exp_slope,
        **{f: getattr(math, f) for f in ("log", "sqrt", "sin", "cos", "tanh", "floor", "pi")},
    }
    exec(source, scope)
    return scope


def statements(targets: Sequence[tuple[str, sp.Expr]], xs: Sequence[sp.Symbol], ps: Sequence[sp.Symbol]) -> Code:
    """``target = expr`` for each, the unknowns read from ``x[i]``, the parameters from ``p[i]``, common
    subexpressions computed once."""
    exprs = [_renamed(e, xs, ps) for _, e in targets]
    common, found = sp.cse(exprs, symbols=sp.numbered_symbols("t"))
    reduced = cast(list[sp.Expr], found)
    py, js = (
        PythonCodePrinter({"fully_qualified_modules": False, "standard": "python3"}),
        JavascriptCodePrinter({"strict": False}),
    )
    out: dict[str, list[str]] = {"py": [], "js": []}
    for name, source in _loads(reduced, common):
        out["py"].append(f"    {name} = {source}")
        out["js"].append(f"const {name} = {source};")
    for s, e in common:
        out["py"].append(f"    {s} = {py.doprint(e)}")
        out["js"].append(f"const {s} = {js.doprint(e)};")
    for (target, _), e in zip(targets, reduced):
        out["py"].append(f"    {target} = {py.doprint(e)}")
        out["js"].append(f"{target} = {js.doprint(e)};")
    return {"py": "\n".join(out["py"]) or "    pass", "js": "\n".join(out["js"])}


def _renamed(e: sp.Expr, xs: Sequence[sp.Symbol], ps: Sequence[sp.Symbol]) -> sp.Expr:
    rename = {s: sp.Symbol(f"x{i}") for i, s in enumerate(xs)} | {s: sp.Symbol(f"p{i}") for i, s in enumerate(ps)}
    return sp.sympify(e).xreplace(rename)


def _loads(reduced: Sequence[sp.Expr], common: Sequence[tuple[sp.Symbol, sp.Expr]]) -> list[tuple[str, str]]:
    """``x3 = x[3]`` for each unknown and parameter used."""
    used = {s.name for e in (*reduced, *(e for _, e in common)) for s in e.free_symbols if isinstance(s, sp.Symbol)}
    return [(name, f"{name[0]}[{name[1:]}]") for name in sorted(used) if name[0] in "xp" and name[1:].isdigit()]


def limited_exp(x: float) -> float:
    return math.exp(x) if x <= EXP_LIMIT else math.exp(EXP_LIMIT) * (1 + x - EXP_LIMIT)


def limited_exp_slope(x: float) -> float:
    return math.exp(min(x, EXP_LIMIT))


class limexp(sp.Function):
    """``exp(x)``, continued by its tangent beyond ``EXP_LIMIT``: Newton's first guesses never overflow."""

    def fdiff(self, argindex=1):
        return dlimexp(self.args[0])

    def _pythoncode(self, printer):
        return f"limexp({printer._print(self.args[0])})"

    def _javascript(self, printer):
        return f"limexp({printer._print(self.args[0])})"


class dlimexp(sp.Function):
    """``limexp``'s derivative."""

    def _pythoncode(self, printer):
        return f"dlimexp({printer._print(self.args[0])})"

    def _javascript(self, printer):
        return f"dlimexp({printer._print(self.args[0])})"


def _junctions(exprs: list[sp.Expr], unknowns: list[sp.Symbol], potentials: Sequence[sp.Expr], exp):
    """Each exponential of what is found becomes ``exp`` of an unknown of its own; one of a junction is
    approached along it (its index, the scale it moves on, and where it bends)."""
    found = sorted({a for e in exprs for a in e.atoms(sp.exp) if symbols_in(a) & set(unknowns)}, key=str)
    out = []
    for k, a in enumerate(found):
        z, mark = sp.Symbol(f"exp_{k}"), sp.Dummy("e")
        marked = [e.xreplace({a: mark}) for e in exprs]
        arg = expr(a.args[0])
        bend = _bend(arg, marked, mark, unknowns, potentials)
        exprs[:] = [e.xreplace({mark: exp(z)}) for e in marked]
        exprs.append(z - arg)
        unknowns.append(z)
        if bend is not None:
            out.append((len(unknowns) - 1, 1.0, bend))
    return out


def _bend(arg: sp.Expr, exprs: Sequence[sp.Expr], mark: sp.Symbol, unknowns, potentials: Sequence[sp.Expr]):
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
    slopes = [abs(float(sp.diff(arg, p))) for p in potentials if isinstance(p, sp.Symbol) and sp.diff(arg, p).is_number]
    nvt = 1 / max((x for x in slopes if x), default=1.0)
    return math.log(nvt / (math.sqrt(2) * c))
