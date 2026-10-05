"""A piece seen only from its two ends (a black box), and the one element it is, if it is one."""

from __future__ import annotations

from collections.abc import Sequence

import sympy as sp

from ..circuit.kind import Kind
from ..circuit.tree import Circuit, Element, free, netlist
from .analysis import DC, Analysis, interpret
from .errors import NotOnePort
from .expressions import subs, symbols_in
from .relation import Equation, Origin, Relation
from .symbols import Symbols
from .system import network

PORT_U, PORT_I = sp.symbols("U_port I_port")
"""A two-ended piece's drop from its first end to its second, and the current in at its first end and out
at its second: as a two-terminal element's U and I."""


def port(s: Symbols, parts: Sequence[int], a: int, b: int, analysis: Analysis) -> Relation | None:
    """The elements ``parts`` between points ``a`` and ``b`` as one relation of ``PORT_U`` and ``PORT_I``,
    everything else inside eliminated. None: no single relation."""
    eqs = _inside(s, parts, a, b, analysis)
    params = {p for k in parts for p in s.params(s.net.parts[k][0]).values()}
    inner = sorted({x for eq in eqs for x in symbols_in(eq)} - params - {PORT_U, PORT_I}, key=str)
    for var in (PORT_U, PORT_I):
        found = sp.solve(eqs, [*inner, var], dict=True)
        if len(found) == 1 and var in found[0]:
            return Relation((PORT_U, PORT_I), (Equation(sp.simplify(var - found[0][var]), Origin("port", (a, b))),))
    return None


def blackbox(piece: Circuit, analysis: Analysis | None = None) -> Relation | None:
    """A 1 → 1 piece seen from its ends, the elements' own names as their parameters."""
    net = netlist(piece)
    if free(piece) != (1, 1) or len(net.left) != 1:
        raise NotOnePort(free(piece))
    s = Symbols(
        net, tuple(e.name or e.kind.prefix for e, _ in net.parts), tuple(sp.Symbol(f"v{n}") for n in range(net.size))
    )
    return port(s, range(len(net.parts)), net.left[0], net.right[0], analysis or DC())


def matches(relation: Relation, kind: Kind, analysis: Analysis | None = None) -> sp.Expr | None:
    """The parameter that makes one element of ``kind`` this very relation (two resistors in series: a
    resistor of R₁ + R₂, found, not told), or None."""
    p = sp.Symbol("p_match")
    if len(kind.terminals) != 2 or len(relation.equations) != 1:
        return None
    its = blackbox(Element(kind, p.name), analysis)
    if its is None:
        return None
    for var, other in ((PORT_U, PORT_I), (PORT_I, PORT_U)):
        mine, theirs = sp.solve(relation.equations[0].expr, var), sp.solve(its.equations[0].expr, var)
        if len(mine) == 1 and len(theirs) == 1:
            return _parameter_making_equal(mine[0], theirs[0], other, p)
    return None


def _inside(s: Symbols, parts: Sequence[int], a: int, b: int, analysis: Analysis) -> list[sp.Expr]:
    """The piece's equations, ``PORT_I`` let in at ``a``, ``b`` the reference, ``PORT_U`` at ``a``."""
    points = sorted({n for k in parts for n in s.net.parts[k][1]} | {a, b})
    ref = s.potentials[b]
    zero = {ref: sp.Integer(0)} if isinstance(ref, sp.Symbol) else {}
    inside = network(s, parts, [n for n in points if n != b], {a: PORT_I})
    return [
        *(subs(interpret(eq.expr, analysis), zero) for eq in inside.equations),
        PORT_U - subs(s.potentials[a], zero),
    ]


def _parameter_making_equal(mine: sp.Expr, theirs: sp.Expr, other: sp.Symbol, p: sp.Symbol) -> sp.Expr | None:
    """``p`` such that ``mine`` = ``theirs`` whatever ``other`` is: each coefficient of ``other`` zero."""
    rest = sp.numer(sp.together(sp.expand(mine - theirs)))
    coefficients = sp.Poly(rest, other).all_coeffs() if rest.has(other) else [rest]
    if any(not c.has(p) and sp.simplify(c) != 0 for c in coefficients):
        return None
    found = sp.solve([c for c in coefficients if c.has(p)], p, dict=True)
    if len(found) == 1 and p in found[0]:
        return sp.simplify(found[0][p])
    return None
