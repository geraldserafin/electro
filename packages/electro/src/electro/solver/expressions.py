"""sympy's own types are loose (``subs`` of a dict, ``replace`` gives ``Basic``): narrowed once, here."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import cast

import sympy as sp


def expr(x: object) -> sp.Expr:
    return cast(sp.Expr, sp.sympify(x))


def subs(x: sp.Expr, values: Mapping[sp.Symbol, sp.Expr] | Mapping[sp.Symbol, float]) -> sp.Expr:
    return cast(sp.Expr, x.subs(list(values.items())))


def replace(x: sp.Expr, f: sp.FunctionClass, by: Callable[[sp.Expr], sp.Expr]) -> sp.Expr:
    return cast(sp.Expr, x.replace(f, by))


def symbols_in(x: sp.Expr) -> set[sp.Symbol]:
    return {s for s in x.free_symbols if isinstance(s, sp.Symbol)}
