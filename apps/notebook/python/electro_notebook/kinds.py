"""What a kind of element is, read off its laws alone: whether it is a source, what a meter reads, whether it
stores energy."""

from __future__ import annotations

import sympy as sp
from electro import DC, Current, D, Element, Voltage


def is_source(e: Element) -> bool:
    """An independent source: a law keeps a term with none of its own quantities in it (``U + E``, ``I − J``),
    read in DC (a capacitor's ``I − C·dU/dt`` keeps none)."""
    own = [x for x in (*e.V.values(), *e.I.values(), *e.inner.values()) if x.is_Symbol]
    zero = dict.fromkeys(own, sp.Integer(0))
    read = DC().reading({})
    return not e.ways and any(sp.simplify(read(q.expr).rewrite(sp.exp).xreplace(zero)) != 0 for q in e.equations)


def reading(e: Element) -> type[Current] | type[Voltage] | None:
    """What a meter reads: of two terminals and no parameter, one law fixing its voltage or its current at zero
    leaves the other free, and that is its value. An ammeter is a wire, a voltmeter a break."""
    if len(e.terminals) != 2 or e.parameters or e.ways or len(e.equations) != 1:
        return None
    a, b = e.terminals
    fixed = e.equations[0].expr.free_symbols
    return Current if fixed == {e.V[a], e.V[b]} else Voltage if fixed == e.I[a].free_symbols else None


def stores(e: Element) -> bool:
    """A law of how something changes (a capacitor's charge, an inductor's flux): it stores energy."""
    laws = [*e.equations, *(q for w in e.ways for q in w.equations)]
    return any(q.expr.has(D) for q in laws)
