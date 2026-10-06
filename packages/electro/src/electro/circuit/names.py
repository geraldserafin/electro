"""A closed circuit's names, as a book gives them: its elements' labels (``R_1``, ``R_2``), and its variables
— ``I_R_1``, ``V_R_1_a``, ``R_1``, ``V_A`` — a renaming of the element's own."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass

import sympy as sp

from .element import Element
from .points import Node
from .quantities import Across, Current, Parameter, Potential, Power, Quantity, Scaled, Sum, Voltage


@dataclass(frozen=True)
class Names:
    """A closed circuit's elements by their labels (``R_1``) and its variables by the names a book gives
    them."""

    labels: Mapping[Element, str]
    to: Mapping[sp.Symbol, sp.Expr]
    points: Mapping[Node, sp.Expr]

    def rename(self, e: sp.Expr) -> sp.Expr:
        """``e`` in the book's names."""
        return e.xreplace(self.to)

    def of(self, q: Quantity | Scaled) -> sp.Expr:
        """A quantity in the named variables."""
        match q:
            case Current(e, at):
                return e.I[at or e.terminals[0]].xreplace(self.to)
            case Voltage(e):
                a, b = e.terminals[:2]
                return (e.V[a] - e.V[b]).xreplace(self.to)
            case Parameter(e, which):
                return e.P[which].xreplace(self.to)
            case Potential(p):
                return self.points.get(p, p.potential)
            case Across(a, b):
                return self.of(Potential(a)) - self.of(Potential(b))
            case Power(e):
                return self.of(Voltage(e)) * self.of(Current(e))
            case Scaled(k, x):
                return k * self.of(x)
            case Sum(terms):
                return sp.Add(*(self.of(t) for t in terms))
        raise TypeError(q)


def names(circuit: Element) -> Names:
    labels = _labels(circuit.members)
    to: dict[sp.Symbol, sp.Expr] = {}
    for e in circuit.members:
        label = labels[e]
        for t, v in e.V.items():
            if isinstance(v, sp.Symbol):
                to[v] = sp.Symbol(f"V_{label}_{t}")
        two = len(e.terminals) == 2
        to |= {
            x: sp.Symbol(f"I_{label}" if two else f"I_{label}_{t}") for t, x in e.I.items() if isinstance(x, sp.Symbol)
        }
        base = e.name or label
        to |= {x: sp.Symbol(f"{w}_{base}" if w else base) for w, x in e.P.items() if isinstance(x, sp.Dummy)}
        to |= {x: sp.Symbol(f"{name}_{label}") for name, x in e.inner.items()}
    points = {}
    every = _points(circuit)
    alike = Counter(p.label for p in every)
    for k, p in enumerate(every, 1):
        if isinstance(p.potential, sp.Dummy):
            points[p] = sp.Symbol(f"V_{p.label}" if p.label and alike[p.label] == 1 else f"V_n{k}")
            to[p.potential] = points[p]
    return Names(labels, to, points)


def _labels(members: tuple[Element, ...]) -> dict[Element, str]:
    """An element's name when no other has it; the others numbered by their prefix in order (``R_1``,
    ``R_2``), past the names taken (``R1`` takes ``R_1`` too)."""
    named = [e.name for e in members]
    unique = {x for x in named if x and named.count(x) == 1}
    taken = {x.replace("_", "") for x in unique}
    counters: Counter[str] = Counter()
    out = {}
    for e in members:
        if e.name in unique:
            out[e] = e.name
            continue
        while True:
            counters[e.prefix] += 1
            label = f"{e.prefix}_{counters[e.prefix]}"
            if label.replace("_", "") not in taken:
                taken.add(label.replace("_", ""))
                out[e] = label
                break
    return out


def _points(circuit: Element) -> list[Node]:
    """Its named points, in the order they are first met."""
    out: list[Node] = []
    for p, _ in circuit.rel.taps:
        if p not in out:
            out.append(p)
    return out
