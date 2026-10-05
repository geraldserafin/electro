"""Windings on one core: a transformer, two coupled inductors. Primary ``p+ p-``, secondary ``s+ s-``,
each winding its own loop."""

from __future__ import annotations

import sympy as sp

from ..kind import Kind, Params, Terminals
from ..time import D


def _transformer(t: Terminals, p: Params) -> list[sp.Expr]:
    """Each winding sees the flux change, the secondary 1/n of it; what the windings' currents leave
    over magnetizes the core. So in DC a winding is a short: the flux does not change."""
    u1, u2, i1, i2 = _windings(t)
    n, flux = p[""], t.inner("flux")
    return [u1 - D(flux), n * u2 - D(flux), flux - p["L_m"] * (i1 + i2 / n), _own_loop(t)]


def _coupled(t: Terminals, p: Params) -> list[sp.Expr]:
    u1, u2, i1, i2 = _windings(t)
    M = p[""]
    return [u1 - p["L1"] * D(i1) - M * D(i2), u2 - M * D(i1) - p["L2"] * D(i2), _own_loop(t)]


def _windings(t: Terminals) -> tuple[sp.Expr, sp.Expr, sp.Expr, sp.Expr]:
    return t.V["p+"] - t.V["p-"], t.V["s+"] - t.V["s-"], t.I["p+"], t.I["s+"]


def _own_loop(t: Terminals) -> sp.Expr:
    return t.I["p+"] + t.I["p-"]


WINDINGS = ("p+", "p-", "s+", "s-")

Transformer = Kind("transformer", "TR", WINDINGS, _transformer, parameters=("", "L_m"), defaults=(("L_m", 10**6),))
"""Of ratio n (U₁ = n·U₂); ``L_m`` its magnetizing inductance, large: magnetizing takes next to nothing."""

Coupled = Kind("coupled", "M", WINDINGS, _coupled, parameters=("", "L1", "L2"))
"""Two inductors ``L1``, ``L2``, and their mutual inductance M (the main parameter)."""
