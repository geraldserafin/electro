"""What an element's laws say of themselves: its ways, whether it is linear, whether it is a source."""

from __future__ import annotations

from collections.abc import Sequence

import sympy as sp

from ..circuit.kind import Case, Cases, Kind, Terminals
from ..circuit.tree import Element
from .analysis import DC, Analysis, interpret
from .expressions import expr, subs


def ways(laws: Sequence[sp.Expr] | Cases) -> tuple[Case, ...]:
    """Laws as ways: plain laws are one way, of no name."""
    if isinstance(laws, Cases):
        return tuple(Case(c.name, _exprs(c.laws), _exprs(c.holds)) for c in laws.cases)
    return (Case("", _exprs(laws)),)


def is_linear(e: Element, analysis: Analysis | None = None) -> bool:
    """Every law of degree one in the element's own quantities, read by ``analysis``. One of several ways
    (piecewise) never is."""
    own = _own_laws(e.kind)
    if own is None:
        return False
    laws, quantities = own
    try:
        return all(
            sp.Poly(sp.expand(interpret(law, analysis or DC())), *quantities).total_degree() <= 1 for law in laws
        )
    except sp.PolynomialError:
        return False


def is_source(e: Element) -> bool:
    """An independent source: a law keeps a term with none of the element's own quantities in it
    (``U + E``, ``I − J``), read in DC (a capacitor's ``I − C·dU/dt`` keeps none)."""
    own = _own_laws(e.kind)
    if own is None:
        return False
    laws, quantities = own
    zero = dict.fromkeys(quantities, sp.Integer(0))
    return any(sp.simplify(subs(interpret(law, DC()), zero)) != 0 for law in laws)


def inner_names(kind: Kind) -> tuple[str, ...]:
    """The names of a kind's own inner quantities (a flux, a state)."""
    return tuple(_read(kind)[2])


def of_ways(kind: Kind) -> bool:
    """One of several ways (a textbook diode): piecewise, decided by assuming."""
    return len(_read(kind)[0]) != 1


def _own_laws(kind: Kind) -> tuple[tuple[sp.Expr, ...], list[sp.Symbol]] | None:
    """A kind's laws over quantities of its own (each terminal's potential and current, its inner ones)
    and those quantities; None when it is of several ways."""
    cases, quantities, inner = _read(kind)
    if len(cases) != 1:
        return None
    return cases[0].laws, [*quantities, *inner.values()]


def _read(kind: Kind) -> tuple[tuple[Case, ...], list[sp.Symbol], dict[str, sp.Symbol]]:
    """A kind's ways over symbols of its own: each terminal's potential and current, and its inner ones by
    name."""
    V = {t: sp.Symbol(f"v_{t}") for t in kind.terminals}
    I = {t: sp.Symbol(f"i_{t}") for t in kind.terminals}
    inner: dict[str, sp.Symbol] = {}
    params = {w: sp.Symbol(f"p_{w}") for w in kind.parameters}
    terminals = Terminals(V, I, lambda name: inner.setdefault(name, sp.Symbol(f"x_{name}")))
    cases = ways(kind.laws(terminals, params))
    return cases, [*V.values(), *I.values()], inner


def _exprs(xs: Sequence[object]) -> tuple[sp.Expr, ...]:
    return tuple(expr(x) for x in xs)
