"""Controlled sources: the control side (``cp``, ``cn``) senses a voltage (taking no current) or the
current through it from ``cp`` to ``cn`` (dropping no voltage); the output (``n``, ``p``) is a source of
a voltage (its + on ``p``) or of a current (out of ``p``), the gain times what is sensed."""

from __future__ import annotations

from collections.abc import Callable

import sympy as sp

from ..kind import Kind, Params, Terminals

TERMINALS = ("cp", "cn", "n", "p")


def _controlled(name: str, out: Callable[[Terminals, sp.Symbol], sp.Expr], senses_current: bool) -> Kind:
    def laws(t: Terminals, p: Params) -> list[sp.Expr]:
        sense = t.across("cp", "cn") if senses_current else t.I["cp"]
        return [sense, t.I["cp"] + t.I["cn"], out(t, p[""])]

    return Kind(name, name.upper(), TERMINALS, laws)


def _u_in(t: Terminals) -> sp.Expr:
    return t.across("cp", "cn")


def _u_out(t: Terminals) -> sp.Expr:
    return t.across("p", "n")


def _i_out(t: Terminals) -> sp.Expr:
    return -t.I["p"]


VCVS = _controlled("vcvs", lambda t, mu: _u_out(t) - mu * _u_in(t), senses_current=False)
VCCS = _controlled("vccs", lambda t, g: _i_out(t) - g * _u_in(t), senses_current=False)
CCVS = _controlled("ccvs", lambda t, r: _u_out(t) - r * t.I["cp"], senses_current=True)
CCCS = _controlled("cccs", lambda t, k: _i_out(t) - k * t.I["cp"], senses_current=True)
