"""Controlled sources: an input that senses a voltage (taking no current) or a current (dropping no
voltage), an output that is a voltage or a current of it."""

from __future__ import annotations

from collections.abc import Callable

import sympy as sp

from ..kind import Kind, Params, Terminals


def _controlled(name: str, out: Callable[[Terminals, sp.Symbol], sp.Expr], senses_current: bool) -> Kind:
    def laws(t: Terminals, p: Params) -> list[sp.Expr]:
        sense = _u_in(t) if senses_current else t.I["in+"]
        return [sense, t.I["in+"] + t.I["in-"], out(t, p[""])]

    return Kind(name, name.upper(), ("in+", "in-", "out+", "out-"), laws)


def _u_in(t: Terminals) -> sp.Expr:
    return t.V["in+"] - t.V["in-"]


def _u_out(t: Terminals) -> sp.Expr:
    return t.V["out+"] - t.V["out-"]


def _i_out(t: Terminals) -> sp.Expr:
    return -t.I["out+"]


VCVS = _controlled("vcvs", lambda t, mu: _u_out(t) - mu * _u_in(t), senses_current=False)
VCCS = _controlled("vccs", lambda t, g: _i_out(t) - g * _u_in(t), senses_current=False)
CCVS = _controlled("ccvs", lambda t, r: _u_out(t) - r * t.I["in+"], senses_current=True)
CCCS = _controlled("cccs", lambda t, k: _i_out(t) - k * t.I["in+"], senses_current=True)
