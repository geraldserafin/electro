"""What an element's own laws say of it, read in no particular circuit: whether it is a source, whether it
is linear, what a meter reads, whether it stores energy."""

from __future__ import annotations

import sympy as sp

from .algebra import symbols_in
from .element import Element
from .frame import DC, Step, interpret
from .quantities import Current, Voltage
from .time import D


def _own(e: Element) -> tuple[list[sp.Expr], list[sp.Symbol]] | None:
    """Its laws over its own quantities (each terminal's potential and current, its inner ones), and those
    quantities; None for an element of several ways."""
    if e.relation.choices:
        return None
    own = [x for x in (*e.V.values(), *e.I.values(), *e.inner.values()) if isinstance(x, sp.Symbol)]
    return [q.expr for q in e.relation.laws], own


def is_source(e: Element) -> bool:
    """An independent source: a law keeps a term with none of its own quantities in it (``U + E``, ``I − J``),
    read in DC (a capacitor's ``I − C·dU/dt`` keeps none)."""
    found = _own(e)
    if found is None:
        return False
    laws, own = found
    zero = dict.fromkeys(own, sp.Integer(0))
    return any(sp.simplify(interpret(law, DC()).xreplace(zero)) != 0 for law in laws)


def is_linear(e: Element, frame: Step | None = None) -> bool:
    """Every law of degree one in its own quantities, read in ``frame``."""
    found = _own(e)
    if found is None:
        return False
    laws, own = found
    try:
        return all(sp.Poly(sp.expand(interpret(law, frame or DC())), *own).total_degree() <= 1 for law in laws)
    except sp.PolynomialError:
        return False


def reading(e: Element) -> type[Current] | type[Voltage] | None:
    """What a meter reads: of two terminals and no parameter, one law fixing its voltage or its current at zero
    leaves the other free, and that is its value. An ammeter is a wire, a voltmeter a break."""
    if len(e.terminals) != 2 or e.parameters or e.relation.choices or len(e.relation.laws) != 1:
        return None
    a, b = e.terminals
    fixed = symbols_in(e.relation.laws[0].expr)
    return Current if fixed == {e.V[a], e.V[b]} else Voltage if fixed == symbols_in(e.I[a]) else None


def stores(e: Element) -> bool:
    """A law of how something changes (a capacitor's charge, an inductor's flux): it stores energy."""
    return any(q.expr.has(D) for q in e.relation.laws) or any(
        q.expr.has(D) for c in e.relation.choices for w in c for q in w.equations
    )
