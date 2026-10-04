"""Circuits as an immutable tree of a few primitives, and its normal form (a netlist), by pure functions.

The prototype of DESIGN.md §9: elements (a kind and the name of their parameter, no value), spiders
(ends meeting in a point), nodes (a point with an identity) and nets (a point everyone named alike
shares); ``>>`` series, ``@`` side by side. Everything else is built from these.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from functools import cache, reduce

import sympy as sp

D = sp.Function("D")  # the derivative in time: an element's law speaks of time only through it

Law = Callable[[sp.Expr, sp.Expr, sp.Expr], sp.Expr]  # (U, I, its parameter) -> what is zero


class JoinsNodes(ValueError):
    """``>>`` would glue two different nodes into one: say it with the same ``Node`` instead."""


class ElementTwice(ValueError):
    """One element in two places: two elements are two objects (``Resistor("R")`` twice)."""


class Circuit:
    """``n → m``: a tree of primitives. Operators are sugar for the functions below."""

    __slots__ = ()

    def __rshift__(self, other: Circuit) -> Circuit:
        return Seq(self, other)

    def __matmul__(self, other: Circuit) -> Circuit:
        return Tensor(self, other)

    def __or__(self, other: Circuit) -> Circuit:
        return parallel(self, other)


@dataclass(frozen=True)
class Kind:
    """What an element is apart from any one of them: its law, said once, in time (``D`` = d/dt).

    ``U`` is the drop from its first end to its second, ``I`` flows from the first to the second.
    """

    name: str
    prefix: str
    unit: str
    law: Law = field(repr=False)
    symmetric: bool = True  # turned around: the same circuit (only its arrows' signs change)

    def __call__(self, name: str | None = None) -> Element:
        return Element(self, name)

    def __repr__(self) -> str:
        return self.name


@dataclass(frozen=True, eq=False)  # (eq=False: an element is itself — two are two, whatever their names)
class Element(Circuit):
    kind: Kind
    name: str | None = None  # its parameter's name: elements named alike share its value

    def __repr__(self) -> str:
        return f"{self.kind.name}({self.name!r})"


@dataclass(frozen=True, eq=False)
class Node(Circuit):
    """A point with an identity (1 → 1): the same object twice is one point. ``label`` only shows."""

    label: str | None = None


@dataclass(frozen=True)
class Net(Circuit):
    """A point every ``Net`` of that name is (1 → 1): GND, VCC."""

    name: str


@dataclass(frozen=True)
class Spider(Circuit):
    """``dom`` ends on the left and ``cod`` on the right, all in one point."""

    dom: int
    cod: int


@dataclass(frozen=True)
class Seq(Circuit):
    first: Circuit
    then: Circuit

    def __post_init__(self) -> None:
        netlist(self)  # (a wrong one is never built: said here, not when it is first used)


@dataclass(frozen=True)
class Tensor(Circuit):
    left: Circuit
    right: Circuit

    def __post_init__(self) -> None:
        netlist(self)


GND = Net("GND")
wire = Spider(1, 1)
cap = Spider(0, 2)  # two ends out of nothing
cup = Spider(2, 0)  # two ends into nothing


def series(*parts: Circuit) -> Circuit:
    return reduce(Seq, parts)


def beside(*parts: Circuit) -> Circuit:
    return reduce(Tensor, parts)


def parallel(f: Circuit, g: Circuit) -> Circuit:
    """Both between the same two points (one end each side: 1 → 1)."""
    return Spider(1, 2) >> (f @ g) >> Spider(2, 1)


def close(f: Circuit) -> Circuit:
    """A 1 → 1 piece's ends joined: ``cap`` makes two ends of one point, ``f`` goes from one, ``cup``
    joins its other end with the second."""
    return cap >> (f @ wire) >> cup


def loop(*parts: Circuit) -> Circuit:
    return close(series(*parts))


# --------------------------------------------------------------------------------------- netlist

Point = Node | Net


@dataclass(frozen=True)
class Netlist:
    """The normal form: points ``0..size-1``, each element between two of them, the ends on each side,
    and which points are a ``Node`` or a ``Net`` (bound: not free ends)."""

    size: int
    parts: tuple[tuple[Element, int, int], ...]
    left: tuple[int, ...]
    right: tuple[int, ...]
    named: tuple[tuple[int, Point], ...] = ()


def _point(dom: int, cod: int, at: Point | None = None) -> Netlist:
    return Netlist(1, (), (0,) * dom, (0,) * cod, ((0, at),) if at is not None else ())


def _shift(net: Netlist, k: int) -> Netlist:
    return Netlist(
        net.size,
        tuple((e, a + k, b + k) for e, a, b in net.parts),
        tuple(n + k for n in net.left),
        tuple(n + k for n in net.right),
        tuple((n + k, p) for n, p in net.named),
    )


def _glued(net: Netlist, pairs: Iterable[tuple[int, int]], left: tuple[int, ...], right: tuple[int, ...]) -> Netlist:
    """Points identified (each pair, and points of the same Node / Net), renumbered in order."""
    parent = list(range(net.size))

    def find(x: int) -> int:
        while parent[x] != x:
            x = parent[x]
        return x

    first: dict[Point, int] = {}
    for n, p in net.named:
        pairs = (*pairs, (n, first.setdefault(p, n)))
    for a, b in pairs:
        parent[find(a)] = find(b)
    roots = sorted({find(n) for n in range(net.size)})
    new = {r: i for i, r in enumerate(roots)}

    def at(n: int) -> int:
        return new[find(n)]

    return Netlist(
        len(roots),
        tuple((e, at(a), at(b)) for e, a, b in net.parts),
        tuple(at(n) for n in left),
        tuple(at(n) for n in right),
        tuple(dict((at(n), p) for n, p in net.named).items()),
    )


@cache
def netlist(c: Circuit) -> Netlist:
    match c:
        case Element():
            return Netlist(2, ((c, 0, 1),), (0,), (1,))
        case Spider(dom, cod):
            return _point(dom, cod)
        case Node() | Net():
            return _point(1, 1, c)
        case Seq(f, g):
            a, b = netlist(f), netlist(g)
            if len(a.right) != len(b.left):
                raise ValueError(f"series: {len(a.right)} ends into {len(b.left)}")
            b = _shift(b, a.size)
            names = dict(a.named) | dict(b.named)
            for x, y in zip(a.right, b.left):
                if x in names and y in names and names[x] != names[y]:
                    raise JoinsNodes(f"{names[x]} and {names[y]}")
            both = Netlist(a.size + b.size, a.parts + b.parts, (), (), a.named + b.named)
            return _checked(_glued(both, zip(a.right, b.left), a.left, b.right))
        case Tensor(f, g):
            a, b = netlist(f), _shift(netlist(g), netlist(f).size)
            both = Netlist(a.size + b.size, a.parts + b.parts, a.left + b.left, a.right + b.right, a.named + b.named)
            return _checked(_glued(both, (), both.left, both.right))
    raise TypeError(f"not a circuit: {c!r}")


def _checked(net: Netlist) -> Netlist:
    elements = [e for e, _, _ in net.parts]
    if len(set(elements)) != len(elements):
        raise ElementTwice(next(e for e in elements if elements.count(e) > 1).name or "an element")
    return net


def free(c: Circuit) -> tuple[int, int]:
    """Its ends not on a ``Node`` / ``Net`` (left, right): the ones still to be connected."""
    net = netlist(c)
    bound = {n for n, _ in net.named}
    return sum(n not in bound for n in net.left), sum(n not in bound for n in net.right)


def is_closed(c: Circuit) -> bool:
    """Nothing left to connect: every end on a point (``a >> E >> R >> a``) or joined (``close``)."""
    return free(c) == (0, 0)


# --------------------------------------------------------------------------------------- elements

Resistor = Kind("resistor", "R", "Ω", lambda U, I, R: U - R * I)
Capacitor = Kind("capacitor", "C", "F", lambda U, I, C: I - C * D(U))
Inductor = Kind("inductor", "L", "H", lambda U, I, L: U - L * D(I))
# a source's + on its second end: V_b − V_a = E, i.e. U = −E; a current source pushes J from a to b
VoltageSource = Kind("voltage_source", "E", "V", lambda U, I, E: U + E, symmetric=False)
CurrentSource = Kind("current_source", "J", "A", lambda U, I, J: I - J, symmetric=False)
