"""What is read of a circuit as it runs, by name, in its elements' own variables: each named point's potential
(``V_A``); of an element of two terminals its current and voltage (``I_R_1``, ``U_R_1``), of more the current
into each terminal (``I_Q_1_c``); its inner quantities (``q_U_1``) and what its kind shows (``U_LCD_1_e``).
The page reads these each frame; a cell reads a run by them (``Trace.reads``)."""

from __future__ import annotations

from functools import cache

import sympy as sp
from electro import Element

from .names import names


def by_element(circuit: Element) -> dict[str, dict[str, tuple[str, sp.Expr]]]:
    """Each element's readings by what it calls them (``U``, ``I``, ``I_c``…): their names and values."""
    labels = names(circuit).labels
    out = {}
    for e in circuit.members:
        label, ts = labels[e], e.terminals
        named: dict[str, tuple[str, sp.Expr]] = {}
        if len(ts) == 2:
            named["I"] = (f"I_{label}", e.I[ts[0]])
            named["U"] = (f"U_{label}", e.V[ts[0]] - e.V[ts[1]])
        else:
            named |= {f"I_{t}": (f"I_{label}_{t}", e.I[t]) for t in (ts[:-1] if e.ground else ts)}
        named |= {name: (f"{name}_{label}", x) for name, x in e.inner.items()}
        for name, what in e.shows:
            value = e.I[what] if isinstance(what, str) else e.V[what[0]] - e.V[what[1]]
            named[name] = (f"{name[0]}_{label}{name[1:]}", value)
        out[label] = named
    return out


@cache
def reads(circuit: Element) -> dict[str, sp.Expr]:
    """Everything read of ``circuit``, by name."""
    points = {str(v): p.potential for p, v in names(circuit).points.items()}
    return points | {called: value for named in by_element(circuit).values() for called, value in named.values()}


def read(name: str, phi) -> sp.Expr:
    """``Trace.reads``: a name as its value."""
    return reads(phi.circuit)[name]
