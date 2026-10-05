"""Ways of wiring pieces together, all built of the primitives."""

from __future__ import annotations

from collections.abc import Iterable
from functools import reduce

from .netlist import Part, Point
from .tree import Circuit, Element, Node, Seq, Spider, Tensor

wire = Spider(1, 1)
"""One end in, one out, one point."""

cap = Spider(0, 2)
"""Two ends out of nothing, one point."""

cup = Spider(2, 0)
"""Two ends into nothing, one point."""


def series(*parts: Circuit) -> Circuit:
    return reduce(Seq, parts)


def beside(*parts: Circuit) -> Circuit:
    return reduce(Tensor, parts)


def parallel(f: Circuit, g: Circuit) -> Circuit:
    """Both between the same two points (one end each side: 1 → 1)."""
    return f | g


def close(f: Circuit) -> Circuit:
    """A 1 → 1 piece with its two ends joined."""
    return cap >> (f @ wire) >> cup


def loop(*parts: Circuit) -> Circuit:
    return close(series(*parts))


def at(e: Element, *points: Circuit) -> Circuit:
    """An element with each terminal on a point, in its terminals' order: ``at(t, b, c, e)``."""
    if len(e.kind.terminals) == 2:
        return points[0] >> e >> points[1]
    return e >> beside(*points)


def rebuild(parts: Iterable[Part], named: Iterable[tuple[int, Point]] = ()) -> Circuit:
    """A closed circuit from its netlist's parts: the inverse of ``netlist``. A point keeps its ``Node`` or
    ``Net``; the others get fresh nodes."""
    shown = dict(named)
    points: dict[int, Point] = {}

    def point(n: int) -> Point:
        return points.setdefault(n, shown.get(n) or Node())

    return beside(*(at(e, *(point(n) for n in ns)) for e, ns in parts))
