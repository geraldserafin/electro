"""A frame's equations as code: what fills their residuals and their Jacobian's nonzero entries — those the
unknowns do not change apart, once a frame — printed once, Python here, JavaScript for the page, and how
to eliminate them (``sparse``), for the engine (``engine.System``) to run on numbers. Two things help Newton, both read
off the shape of the laws, never any element's: every exponential grows along its tangent far out, and one
that is tiny at zero but steep (as a p-n junction's, whatever has one) is approached along it, as SPICE does.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import cast

import sympy as sp
from sympy.printing.jscode import JavascriptCodePrinter
from sympy.printing.pycode import PythonCodePrinter

from .algebra import expr, subs, symbols_in
from .engine import System, limited_exp, limited_exp_slope, newton
from .sparse import shape

Code = dict[str, str]
"""``"py"`` and ``"js"``: the same statements in each."""


JUNCTION = 1e-6
"""An exponential less than this at zero is approached along it."""


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
    potentials: Sequence[sp.Expr],
    limited: bool = True,
    currents: Sequence[sp.Expr] = (),
    sample: Sequence[float] | None = None,
) -> Compiled:
    """``exprs`` = 0 as code; ``potentials``: the points', to tell a junction's scale; ``currents``: what
    the laws say flows (a junction's own current, before any equation was scaled). ``limited``: every
    exponential continued by its tangent far out (a model that runs); else exactly the law. ``sample``: the
    parameters of a frame like those it will run (by default all 1), whose numbers choose the pivots."""
    exprs, unknowns = list(exprs), list(unknowns)
    junctions = _junctions(exprs, unknowns, potentials, limexp if limited else sp.exp, currents)
    place = {u: j for j, u in enumerate(unknowns)}
    entries, values = [], []
    for i, e in enumerate(exprs):
        for u in sorted(symbols_in(e) & set(place), key=lambda u: place[u]):
            d = expr(sp.diff(e, u))
            if d != 0:
                entries.append((i, place[u]))
                values.append(d)
    dynamic = [bool(symbols_in(d) & set(place)) for d in values]
    constant = statements([(f"A[{k}]", d) for k, (d, m) in enumerate(zip(values, dynamic)) if not m], unknowns, params)
    moving = statements(
        [(f"F[{i}]", e) for i, e in enumerate(exprs)]
        + [(f"A[{k}]", d) for k, (d, m) in enumerate(zip(values, dynamic)) if m],
        unknowns,
        params,
    )
    scope = python(f"def jconst(p, A):\n{constant['py']}\n\ndef jdyn(x, p, F, A):\n{moving['py']}\n")
    A = [0.0] * len(entries)
    p = list(sample) if sample is not None else [1.0] * len(params)
    with _quiet():
        scope["jconst"](p, A)
        scope["jdyn"]([0.0] * len(unknowns), p, [0.0] * len(exprs), A)
    return Compiled(unknowns, list(params), constant, moving, shape(len(unknowns), entries, A, dynamic), junctions)


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
    return sp.sympify(e).xreplace(rename)


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


def _junctions(exprs: list[sp.Expr], unknowns: list[sp.Symbol], potentials: Sequence[sp.Expr], exp, currents=()):
    """Each exponential of what is found becomes ``exp`` of an unknown of its own; one of a junction is
    approached along it (its index, the scale it moves on, and where it bends)."""
    found = sorted({a for e in exprs for a in e.atoms(sp.exp) if symbols_in(a) & set(unknowns)}, key=str)
    out = []
    for k, a in enumerate(found):
        z, mark = sp.Symbol(f"exp_{k}"), sp.Dummy("e")
        marked = [e.xreplace({a: mark}) for e in exprs]
        arg = expr(a.args[0])
        own = [c.xreplace({a: mark}) for c in currents if c.has(a)]
        bend = _bend(arg, own or marked, mark, unknowns, potentials, smallest=bool(own))
        exprs[:] = [e.xreplace({mark: exp(z)}) for e in marked]
        exprs.append(z - arg)
        unknowns.append(z)
        if bend is not None:
            out.append((len(unknowns) - 1, 1.0, bend))
    return out


def _bend(
    arg: sp.Expr, exprs: Sequence[sp.Expr], mark: sp.Symbol, unknowns, potentials: Sequence[sp.Expr], smallest=False
):
    """Where a junction's exponential bends, in its own argument (SPICE's V_crit, over n·V_T); None: not a
    junction. ``smallest``: ``exprs`` say what flows, the junction's own current the least of them."""
    at_zero = dict.fromkeys(unknowns, 0)
    scale = [abs(subs(sp.diff(e, mark), at_zero)) for e in exprs if e.has(mark)]
    numbers = [float(c) for c in scale if c.is_number and c.is_real and c.is_finite]
    zero = subs(arg, at_zero)
    if not numbers or not (zero.is_number and zero.is_real and zero.is_finite):
        return None
    c = min(x for x in numbers if x) if smallest and any(numbers) else max(numbers)
    if c == 0 or c * math.exp(min(float(zero), 700)) >= JUNCTION:
        return None
    slopes = [
        abs(float(d)) for p in potentials if isinstance(p, sp.Symbol) and (d := sp.diff(arg, p)).is_number and d.is_real
    ]
    nvt = 1 / max((x for x in slopes if x), default=1.0)
    bend = math.log(nvt / (math.sqrt(2) * c))
    return bend if bend > 0 else None
