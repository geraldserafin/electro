"""Expressions as statements in Python and in JavaScript: the page's engine runs the one, ``run`` the other."""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

import sympy as sp
from sympy.printing.jscode import JavascriptCodePrinter
from sympy.printing.pycode import PythonCodePrinter

Code = dict[str, str]
"""``"py"`` and ``"js"``: the same statements in each."""


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
