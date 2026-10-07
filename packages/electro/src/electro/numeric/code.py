"""A frame's equations as code for the engine (``engine.System``): one function fills the Jacobian's entries
the unknowns do not change (once a frame), another the residuals and the rest; both printed as Python here and
as JavaScript for the page. ``sparse`` chooses the order they are eliminated in.

Two things help Newton: every exponential continues along its tangent far out (``limexp``), and a p-n
junction's exponential (``pn``) is approached along its bend, as SPICE does."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import cast

import sympy as sp
from sympy.printing.jscode import JavascriptCodePrinter
from sympy.printing.pycode import PythonCodePrinter

from ..elements.physics import pn
from .engine import System, limited_exp, limited_exp_slope, newton
from .sparse import shape

Code = dict[str, str]
"""``"py"`` and ``"js"``: the same statements in each."""


@dataclass
class Compiled:
    """Equations as code over ``unknowns`` and ``params``: ``constant`` fills the Jacobian's entries the
    unknowns do not change, ``moving`` the residuals and the rest; ``shape`` how they are eliminated.
    ``junctions``: each junction's unknown, the scale it moves on and where it bends."""

    unknowns: list[sp.Symbol]
    params: list[sp.Symbol]
    constant: Code
    moving: Code
    shape: dict
    junctions: list[tuple[int, float, float]]
    _system: System | None = field(default=None, repr=False)

    @property
    def system(self) -> System:
        if self._system is None:
            scope = python(f"def jconst(p, A):\n{self.constant['py']}\n\ndef jdyn(x, p, F, A):\n{self.moving['py']}\n")
            self._system = System(self.shape, scope["jconst"], scope["jdyn"])
        return self._system

    def newton(self, x0: Sequence[float], p: Sequence[float]) -> list[float] | None:
        return newton(self.system, x0, p, self.junctions)


def compile_equations(
    exprs: Sequence[sp.Expr],
    unknowns: Sequence[sp.Symbol],
    params: Sequence[sp.Symbol],
    limited: bool = True,
    sample: Sequence[float] | None = None,
) -> Compiled:
    """``exprs`` = 0 as code. ``limited``: every exponential continued along its tangent far out; else exactly
    the law. ``sample``: the parameters of a frame like those it will run (by default all 1); its numbers choose
    the pivots."""
    exprs, unknowns, junctions = _junctions(list(exprs), list(unknowns), limexp if limited else sp.exp)
    entries = _jacobian(exprs, unknowns)
    moves = [bool(d.free_symbols & set(unknowns)) for _, _, d in entries]
    constant = statements([(f"A[{k}]", d) for k, (_, _, d) in enumerate(entries) if not moves[k]], unknowns, params)
    residuals = [(f"F[{i}]", e) for i, e in enumerate(exprs)]
    moving = statements(
        residuals + [(f"A[{k}]", d) for k, (_, _, d) in enumerate(entries) if moves[k]], unknowns, params
    )
    numbers = _sample(constant, moving, len(unknowns), len(entries), sample or [1.0] * len(params))
    plan = shape(len(unknowns), [(i, j) for i, j, _ in entries], numbers, moves)
    plan["linear"] = plan["linear"] and not _switches(exprs, unknowns)
    return Compiled(unknowns, list(params), constant, moving, plan, junctions)


def _jacobian(exprs: list[sp.Expr], unknowns: list[sp.Symbol]) -> list[tuple[int, int, sp.Expr]]:
    """Its nonzero entries: row, column, derivative."""
    place = {u: j for j, u in enumerate(unknowns)}
    entries = []
    for i, e in enumerate(exprs):
        for u in sorted(e.free_symbols & set(place), key=lambda u: place[u]):
            if (d := sp.diff(e, u)) != 0:
                entries.append((i, place[u], d))
    return entries


def _sample(constant: Code, moving: Code, n: int, m: int, p: Sequence[float]) -> list[float]:
    """The Jacobian's entries in a sample frame, the unknowns 0; what overflows stays very large."""
    scope = python(f"def jconst(p, A):\n{constant['py']}\n\ndef jdyn(x, p, F, A):\n{moving['py']}\n")
    A = [0.0] * m
    with _quiet():
        scope["jconst"](list(p), A)
        scope["jdyn"]([0.0] * n, list(p), [0.0] * n, A)
    return A


def _switches(exprs: list[sp.Expr], unknowns: list[sp.Symbol]) -> bool:
    """A function or a ``when`` of an unknown: Newton needs more than one step, though the Jacobian moves not."""
    return any(f.free_symbols & set(unknowns) for e in exprs for f in e.atoms(sp.Function, sp.Piecewise))


class _quiet:
    """A sample frame's numbers as they come: what overflows or divides by zero is very large."""

    def __enter__(self):
        return self

    def __exit__(self, kind, err, tb):
        return kind in (OverflowError, ZeroDivisionError)


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
    return plain(sp.sympify(e)).xreplace(rename)


def plain(e: sp.Expr) -> sp.Expr:
    """A junction's exponential as any other: what is read of a frame needs no Newton."""
    return e.replace(lambda a: isinstance(a, pn), lambda a: limexp(a.args[0]))


def _loads(reduced: Sequence[sp.Expr], common: Sequence[tuple[sp.Symbol, sp.Expr]]) -> list[tuple[str, str]]:
    """``x3 = x[3]`` for each unknown and parameter used."""
    used = {s.name for e in (*reduced, *(e for _, e in common)) for s in e.free_symbols if isinstance(s, sp.Symbol)}
    return [(name, f"{name[0]}[{name[1:]}]") for name in sorted(used) if name[0] in "xp" and name[1:].isdigit()]


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


def _junctions(exprs: list[sp.Expr], unknowns: list[sp.Symbol], exp):
    """Each p-n junction's exponential becomes ``exp`` of an unknown of its own, ``exp_k`` (one equation more:
    ``exp_k`` = its exponent), so Newton can limit how far it moves. The equations, the unknowns, and each
    junction's unknown, the scale it moves on and where it bends."""
    junctions = []
    for k, a in enumerate(sorted({a for e in exprs for a in e.atoms(pn) if a.free_symbols & set(unknowns)}, key=str)):
        z = sp.Symbol(f"exp_{k}")
        exprs = [e.xreplace({a: exp(z)}) for e in exprs] + [z - a.args[0]]
        unknowns = [*unknowns, z]
        if (bend := _bend(a)) > 0:
            junctions.append((len(unknowns) - 1, 1.0, bend))
    return _exponentials(exprs, unknowns, exp), unknowns, junctions


def _bend(a: pn) -> float:
    """Where a junction's exponential bends, in its exponent (SPICE's V_crit over n·V_T): ln(n·V_T / (√2·I))."""
    _, i, nvt = a.args
    return math.log(float(nvt) / (math.sqrt(2) * float(i))) if i.is_number and nvt.is_number else 0.0


def _exponentials(exprs: list[sp.Expr], unknowns: list[sp.Symbol], exp) -> list[sp.Expr]:
    """Every other exponential of an unknown as ``exp`` too."""
    found = set(unknowns)
    return [
        e.replace(lambda a: isinstance(a, sp.exp) and bool(a.free_symbols & found), lambda a: exp(a.args[0]))
        for e in exprs
    ]
