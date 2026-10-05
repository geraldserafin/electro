"""A circuit as an immutable tree of a few primitives (DESIGN.md §9), and its netlist.

``a >> b`` puts ``b`` after ``a`` (``a``'s right ends onto ``b``'s left ends), ``a @ b`` side by side,
``a | b`` both between the same two points.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cache
from typing import TYPE_CHECKING

from .netlist import Netlist, in_series, lone_element, lone_point, side_by_side

if TYPE_CHECKING:
    from .kind import Kind


class BadName(ValueError):
    """A name with more than letters, digits and ``_`` in it: nothing else gets into the equations, the
    code made of them or the formulas drawn."""


class Circuit:
    """``n → m``: ``n`` ends on the left, ``m`` on the right."""

    __slots__ = ()

    def __rshift__(self, other: Circuit) -> Circuit:
        return Seq(self, other)

    def __matmul__(self, other: Circuit) -> Circuit:
        return Tensor(self, other)

    def __or__(self, other: Circuit) -> Circuit:
        return Spider(1, 2) >> (self @ other) >> Spider(2, 1)


@dataclass(frozen=True, eq=False)
class Element(Circuit):
    """An element is itself: two are two, whatever their names. ``name`` names its parameter, so elements
    named alike share its value."""

    kind: Kind
    name: str | None = None

    def __post_init__(self) -> None:
        if self.name is not None and not self.name.isidentifier():
            raise BadName(self.name)

    def __repr__(self) -> str:
        return f"{self.kind.name}({self.name!r})"


@dataclass(frozen=True, eq=False)
class Node(Circuit):
    """A point with an identity (1 → 1): the same object twice is one point. ``label`` only shows."""

    label: str | None = None

    def __post_init__(self) -> None:
        if self.label is not None and not re.fullmatch(r"\w+", self.label):
            raise BadName(self.label)


@dataclass(frozen=True)
class Net(Circuit):
    """A point every ``Net`` of that name is (1 → 1): GND, VCC."""

    name: str

    def __post_init__(self) -> None:
        if not re.fullmatch(r"\w+", self.name):
            raise BadName(self.name)


@dataclass(frozen=True)
class Spider(Circuit):
    """``dom`` ends on the left and ``cod`` on the right, all in one point."""

    dom: int
    cod: int


@dataclass(frozen=True)
class Seq(Circuit):
    """``first``, then ``then``. Checked as it is built: a wrong one never exists."""

    first: Circuit
    then: Circuit

    def __post_init__(self) -> None:
        netlist(self)


@dataclass(frozen=True)
class Tensor(Circuit):
    """``left`` and ``right`` side by side. Checked as it is built."""

    left: Circuit
    right: Circuit

    def __post_init__(self) -> None:
        netlist(self)


GND = Net("GND")


@cache
def netlist(c: Circuit) -> Netlist:
    match c:
        case Element(kind):
            return lone_element(c, len(kind.terminals))
        case Spider(dom, cod):
            return lone_point(dom, cod)
        case Node() | Net():
            return lone_point(1, 1, c)
        case Seq(first, then):
            return in_series(netlist(first), netlist(then))
        case Tensor(left, right):
            return side_by_side(netlist(left), netlist(right))
    raise TypeError(f"not a circuit: {c!r}")


def free(c: Circuit) -> tuple[int, int]:
    """How many of its ends, left and right, are not on a ``Node`` or ``Net``: still to be connected."""
    net = netlist(c)
    bound = {n for n, _ in net.named}
    return sum(n not in bound for n in net.left), sum(n not in bound for n in net.right)


def is_closed(c: Circuit) -> bool:
    """Nothing left to connect: every end on a point (``a >> E >> R >> a``) or joined (``close``)."""
    return free(c) == (0, 0)
