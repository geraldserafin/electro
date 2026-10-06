"""The spiders and the crossing by name, and a circuit rebuilt from its netlist."""

from __future__ import annotations

from collections.abc import Iterable
from functools import reduce
from operator import matmul

from .netlist import Part, Point
from .tree import Circuit, Element, Node, Spider, Swap

wire = Spider(1, 1)
"""One end in, one out, one point."""

cap = Spider(0, 2)
"""Two ends out of nothing, one point."""

cup = Spider(2, 0)
"""Two ends into nothing, one point."""

swap = Swap()
"""Two ends crossing."""


def placed(e: Element, points: Iterable[Circuit]) -> Circuit:
    """An element with each end on a point, in its terminals' order: ``a >> e >> b``, or ``e >> (a @ b @ c)``."""
    ps = tuple(points)
    return ps[0] >> e >> ps[1] if len(e.kind.terminals) == 2 else e >> reduce(matmul, ps)


def rebuild(parts: Iterable[Part], named: Iterable[tuple[int, Point]] = ()) -> Circuit:
    """A closed circuit from its netlist's parts: the inverse of ``netlist``. A point keeps its ``Node`` or
    ``Net``; the others get fresh nodes."""
    shown = dict(named)
    points: dict[int, Point] = {}

    def point(n: int) -> Point:
        return points.setdefault(n, shown.get(n) or Node())

    return reduce(matmul, (placed(e, (point(n) for n in ns)) for e, ns in parts))
