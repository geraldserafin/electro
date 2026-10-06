"""Where elements meet: points, a crossing, named points. Each is an element too — its laws one potential at
all its ends and Kirchhoff — and all its variables only join: fresh wherever it is used."""

from __future__ import annotations

import re

import sympy as sp

from .algebra import Equation, Origin
from .element import NAMED, POTENTIALS, BadName, Element, End, Relation


class Spider(Element):
    """``dom`` ends in on the left and ``cod`` out on the right, all one point: one potential, what comes in
    goes out."""

    kind, prefix = "point", "P"

    def __init__(self, dom: int, cod: int) -> None:
        self.name, self.members, self.dom, self.cod = None, (), dom, cod
        v = sp.Dummy("v")
        POTENTIALS.add(v)
        ins, outs = [sp.Dummy("i") for _ in range(dom)], [sp.Dummy("i") for _ in range(cod)]
        kcl = (Equation(sp.Add(*ins) - sp.Add(*outs), Origin("kcl", None)),) if ins or outs else ()
        joining = frozenset([v, *ins, *outs])
        self.relation = Relation(tuple(End(v, i) for i in ins), tuple(End(v, i) for i in outs), kcl, joining=joining)

    def __repr__(self) -> str:
        return f"Spider({self.dom}, {self.cod})"


class Swap(Element):
    """Two ends crossing (2 → 2): with points, caps and cups it joins any ends to any others."""

    kind, prefix = "swap", "S"

    def __init__(self) -> None:
        self.name, self.members = None, ()
        a, b = End(sp.Dummy("v"), sp.Dummy("i")), End(sp.Dummy("v"), sp.Dummy("i"))
        POTENTIALS.update((a.v, b.v))
        self.relation = Relation((a, b), (b, a), joining=frozenset([a.v, a.i, b.v, b.i]))


class Node(Element):
    """A named point (1 → 1): the same object wherever it is used is one point; ``label`` only shows. Its
    potential is one variable everywhere; the currents into it meet when the circuit is whole."""

    kind, prefix = "node", "N"

    def __init__(self, label: str | None = None) -> None:
        if label is not None and not re.fullmatch(r"\w+", label):
            raise BadName(label)
        self.name, self.label, self.members = None, label, ()
        self.potential = sp.Dummy(f"V_{label or ''}")
        NAMED.add(self.potential)
        POTENTIALS.add(self.potential)

    @property
    def relation(self) -> Relation:
        into, out = sp.Dummy("i"), sp.Dummy("i")
        v = self.potential
        return Relation((End(v, into),), (End(v, out),), taps=((self, into - out),), joining=frozenset([into, out]))

    def __repr__(self) -> str:
        return f"Node({self.label!r})"


class Net(Node):
    """A point every ``Net`` of that name is: ``GND`` (potential 0), ``VCC``."""

    def __init__(self, name: str) -> None:
        if not re.fullmatch(r"\w+", name):
            raise BadName(name)
        self.name, self.label, self.members = None, name, ()
        self.potential = sp.Integer(0) if name == "GND" else sp.Symbol(f"V_{name}")
        if name != "GND":
            NAMED.add(self.potential)
            POTENTIALS.add(self.potential)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Net) and other.label == self.label

    def __hash__(self) -> int:
        return hash(("Net", self.label))

    def __repr__(self) -> str:
        return f"Net({self.label!r})"


GND = Net("GND")
wire = Spider(1, 1)
cap = Spider(0, 2)
cup = Spider(2, 0)
swap = Swap()
