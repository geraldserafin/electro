"""What a kind of element is, read off its laws alone: what a meter reads, whether it stores energy."""

from __future__ import annotations

from electro import Current, D, Element, Voltage
from electro.circuit.algebra import symbols_in


def reading(e: Element) -> type[Current] | type[Voltage] | None:
    """What a meter reads: of two terminals and no parameter, one law fixing its voltage or its current at zero
    leaves the other free, and that is its value. An ammeter is a wire, a voltmeter a break."""
    laws = e.rel.laws
    if len(e.terminals) != 2 or e.parameters or laws.choices or len(laws.equations) != 1:
        return None
    a, b = e.terminals
    fixed = symbols_in(laws.equations[0].expr)
    return Current if fixed == {e.V[a], e.V[b]} else Voltage if fixed == symbols_in(e.I[a]) else None


def stores(e: Element) -> bool:
    """A law of how something changes (a capacitor's charge, an inductor's flux): it stores energy."""
    return any(x.has(D) for x in e.rel.laws.expressions())
