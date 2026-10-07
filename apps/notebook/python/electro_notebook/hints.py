"""What would help, when a circuit's data do not do: which one datum more would pin down what is sought, and
which of the data clash."""

from __future__ import annotations

import sympy as sp
from electro import Contradiction, Current, MissingData, Parameter, Voltage


def pinning(err: MissingData) -> list:
    """Quantities each of which, given, would pin down what is lacking (when one datum is needed)."""
    s = err.solution
    free = sorted({x for e in err.lacking for x in e.free_symbols} & s.unknowns, key=str)
    if len(free) != 1:
        return []
    (x,), lacking = free, sp.Add(*err.lacking)
    out = []
    for e in s.circuit.members:
        for q in [
            *((Voltage(e), Current(e)) if len(e.terminals) == 2 else ()),
            *(Parameter(e, w) for w in e.parameters),
        ]:
            v = s.of(q)
            if x not in v.free_symbols:
                continue
            roots = sp.solve(v - sp.Dummy("k"), x)
            if len(roots) == 1 and not lacking.subs(x, roots[0]).free_symbols & s.unknowns:
                out.append(q)
    return out


def clashing(err: Contradiction) -> dict:
    """The data that clash, as given: those among the equations that cannot all hold."""
    return {key: err.values[key] for key in err.data if key in err.values}
