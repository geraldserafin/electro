"""A circuit's normal form, and how pieces are put together in it.

Points are numbered ``0 … size−1``; each element sits on the point of each of its terminals. In series the
touching ends of two pieces become one point, side by side none do, and a ``Node`` or ``Net`` is one point
wherever it appears.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeAlias

if TYPE_CHECKING:
    from .tree import Element, Net, Node

Point: TypeAlias = "Node | Net"
Part: TypeAlias = "tuple[Element, tuple[int, ...]]"


class JoinsNodes(ValueError):
    """``>>`` would glue two different nodes into one: say it with the same ``Node`` instead."""


class ElementTwice(ValueError):
    """One element in two places: two elements are two objects (``Resistor("R")`` twice)."""


@dataclass(frozen=True)
class Netlist:
    """The points, the elements on them, the free ends on each side, and which points are a ``Node`` or a
    ``Net``."""

    size: int
    parts: tuple[Part, ...]
    left: tuple[int, ...]
    right: tuple[int, ...]
    named: tuple[tuple[int, Point], ...] = ()


def lone_point(dom: int, cod: int, at: Point | None = None) -> Netlist:
    """One point with ``dom`` ends on the left and ``cod`` on the right; ``at`` is the Node or Net it is."""
    return Netlist(1, (), (0,) * dom, (0,) * cod, ((0, at),) if at is not None else ())


def crossing() -> Netlist:
    """Two points, each from a left end to the other right end."""
    return Netlist(2, (), (0, 1), (1, 0))


def lone_element(e: Element, terminals: int, ground: Point | None = None) -> Netlist:
    """One element on points of its own. With two terminals it is 1 → 1; with any other number all its
    ends are on the right (0 → n). ``ground``: its last terminal on it, no end of its own."""
    ends = tuple(range(terminals))
    if terminals == 2:
        return Netlist(2, ((e, ends),), (0,), (1,))
    if ground is not None:
        return Netlist(terminals, ((e, ends),), (), ends[:-1], ((ends[-1], ground),))
    return Netlist(terminals, ((e, ends),), (), ends)


def in_series(a: Netlist, b: Netlist) -> Netlist:
    if len(a.right) != len(b.left):
        raise ValueError(f"series: {len(a.right)} ends into {len(b.left)}")
    b = _shifted(b, a.size)
    _refuse_joining_nodes(a, b)
    both = Netlist(a.size + b.size, a.parts + b.parts, (), (), a.named + b.named)
    return _each_element_once(_glued(both, zip(a.right, b.left), a.left, b.right))


def side_by_side(a: Netlist, b: Netlist) -> Netlist:
    b = _shifted(b, a.size)
    both = Netlist(a.size + b.size, a.parts + b.parts, a.left + b.left, a.right + b.right, a.named + b.named)
    return _each_element_once(_glued(both, (), both.left, both.right))


def representatives(size: int, pairs: Iterable[tuple[int, int]]) -> list[int]:
    """Each of ``0 … size−1``'s representative once the two of each pair are one: those of one
    representative are one."""
    parent = list(range(size))

    def find(x: int) -> int:
        while parent[x] != x:
            x = parent[x]
        return x

    for a, b in pairs:
        parent[find(a)] = find(b)
    return [find(n) for n in range(size)]


def pieces(net: Netlist) -> list[int]:
    """Each point's piece, as a representative: points joined through elements are one piece."""
    return representatives(net.size, ((n, ns[0]) for _, ns in net.parts for n in ns[1:]))


def _shifted(net: Netlist, k: int) -> Netlist:
    return Netlist(
        net.size,
        tuple((e, tuple(n + k for n in ns)) for e, ns in net.parts),
        tuple(n + k for n in net.left),
        tuple(n + k for n in net.right),
        tuple((n + k, p) for n, p in net.named),
    )


def _refuse_joining_nodes(a: Netlist, b: Netlist) -> None:
    names = dict(a.named) | dict(b.named)
    for x, y in zip(a.right, b.left):
        if x in names and y in names and names[x] != names[y]:
            raise JoinsNodes(f"{names[x]} and {names[y]}")


def _glued(net: Netlist, pairs: Iterable[tuple[int, int]], left: tuple[int, ...], right: tuple[int, ...]) -> Netlist:
    """Points made one (each pair, and the points of one Node or Net), renumbered in order."""
    rep = representatives(net.size, (*pairs, *_alike(net)))
    number = {r: i for i, r in enumerate(sorted(set(rep)))}

    def to(n: int) -> int:
        return number[rep[n]]

    return Netlist(
        len(number),
        tuple((e, tuple(to(n) for n in ns)) for e, ns in net.parts),
        tuple(to(n) for n in left),
        tuple(to(n) for n in right),
        tuple(dict((to(n), p) for n, p in net.named).items()),
    )


def _alike(net: Netlist) -> list[tuple[int, int]]:
    """Each point of a Node or Net paired with the first point of the same."""
    first: dict[Point, int] = {}
    return [(n, first.setdefault(p, n)) for n, p in net.named]


def _each_element_once(net: Netlist) -> Netlist:
    elements = [e for e, _ in net.parts]
    if len(set(elements)) != len(elements):
        raise ElementTwice(next(e for e in elements if elements.count(e) > 1).name or "an element")
    return net


def labels(net: Netlist) -> tuple[str, ...]:
    """An element's name when no other element has it; the others numbered by their prefix in order
    (``R_1``, ``R_2``), past the names taken (``R1`` takes ``R_1`` too)."""
    names = [e.name for e, _ in net.parts]
    unique = {n for n in names if n and names.count(n) == 1}
    taken = {_loose(n) for n in unique}
    counters: Counter[str] = Counter()

    def numbered(prefix: str) -> str:
        while True:
            counters[prefix] += 1
            label = f"{prefix}_{counters[prefix]}"
            if _loose(label) not in taken:
                taken.add(_loose(label))
                return label

    return tuple(e.name if e.name in unique else numbered(e.kind.prefix) for e, _ in net.parts)


def _loose(name: str) -> str:
    return name.replace("_", "")
