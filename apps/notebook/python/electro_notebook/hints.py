"""What would help, when a circuit's data do not do: which one datum more would pin down what is sought, and
which of the data clash."""

from __future__ import annotations

import sympy as sp
from electro import Contradiction, Current, MissingData, Parameter, Voltage


def pinning(err: MissingData) -> list:
    """Quantities each of which, given, would pin down what is lacking (when one datum is missing)."""
    s = err.solution
    free = sorted({x for e in err.lacking for x in e.free_symbols} & s.unknowns, key=str)
    if len(free) != 1:
        return []
    return [q for q in _measurable(s.circuit) if _pins(s, q, free[0], sp.Add(*err.lacking))]


def _measurable(circuit) -> list:
    """Each element's parameters, and of a two-terminal one its voltage and current."""
    out = []
    for e in circuit.members:
        out += [Voltage(e), Current(e)] if len(e.terminals) == 2 else []
        out += [Parameter(e, w) for w in e.parameters]
    return out


def _pins(s, q, x: sp.Symbol, lacking: sp.Expr) -> bool:
    """Whether ``q`` given would fix ``x`` to one value, and with it what is lacking."""
    v = s.of(q)
    if x not in v.free_symbols:
        return False
    roots = sp.solve(v - sp.Dummy("k"), x)
    return len(roots) == 1 and not lacking.subs(x, roots[0]).free_symbols & s.unknowns


def clashing(err: Contradiction) -> dict:
    """The data that clash, as given: those among the equations that cannot all hold."""
    return {key: err.values[key] for key in err.data if key in err.values}
