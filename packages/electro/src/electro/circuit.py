"""A circuit is a drawing: elements, the points their terminals are on, and its free ends. Joining circuits
only says which points are the same:

- ``f >> g``: ``f``'s right ends are ``g``'s left ends;
- ``f @ g``: side by side;
- ``f | g``, ``~f``, ``-f``: made of ``>>`` and ``@`` with ``Spider``s (one point, any number of ends).

Nothing is solved while joining. A closed circuit's laws (``closed``) are each element's laws on the potentials
of its points, and Kirchhoff at every point; ``solve`` and ``simulate`` work them out."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterator, Mapping
from typing import TYPE_CHECKING

import sympy as sp

from .errors import BadName, ElementTwice, JoinsNodes, NotClosed, WrongEnds
from .laws import Equation, Laws, Origin

if TYPE_CHECKING:
    from .element import Element


class Point:
    """Where terminals meet; ``potential``: one variable for all of them."""

    def __init__(self, potential: sp.Expr | None = None) -> None:
        self.potential = potential if potential is not None else sp.Dummy("v")

    def __repr__(self) -> str:
        return f"Point({self.potential})"


Parts = tuple[tuple["Element", tuple[Point, ...]], ...]


class Circuit:
    """``parts``: each element and the points of its drawn terminals, in order; ``left`` and ``right``: the
    points other circuits join it at."""

    def __init__(self, parts: Parts = (), left: tuple[Point, ...] = (), right: tuple[Point, ...] = ()) -> None:
        elements = [e for e, _ in parts]
        if len({id(e) for e in elements}) != len(elements):
            raise ElementTwice(next(e for e in elements if elements.count(e) > 1).name or "an element")
        self.parts, self.left, self.right = parts, left, right

    @property
    def members(self) -> tuple[Element, ...]:
        return tuple(e for e, _ in self.parts)

    def ends(self) -> Iterator[tuple[Element, str, Point]]:
        """Every element's every drawn terminal, and the point it is on."""
        for e, at in self.parts:
            yield from ((e, t, p) for t, p in zip(e.drawn, at))

    def renamed(self, to: Mapping[Point, Point]) -> Circuit:
        """The same circuit, each point replaced as ``to`` says."""

        def new(p: Point) -> Point:
            return to.get(p, p)

        parts = tuple((e, tuple(map(new, at))) for e, at in self.parts)
        return Circuit(parts, tuple(map(new, self.left)), tuple(map(new, self.right)))

    def piece(self) -> Circuit:
        """The circuit where it is used. An element is in one place only; points with no element on them (a
        spider, what is made of spiders) are new wherever they are used."""
        if self.parts:
            return self
        return self.renamed({p: Point() for p in (*self.left, *self.right) if not isinstance(p, Node)})

    # Joining

    def __rshift__(self, other: Circuit) -> Circuit:
        a, b = self.piece(), other.piece()
        if len(a.right) != len(b.left):
            raise WrongEnds(len(a.right), len(b.left))
        both = Circuit(a.parts + b.parts, a.left, b.right)
        return both.renamed(_same(zip(a.right, b.left)))

    def __matmul__(self, other: Circuit) -> Circuit:
        a, b = self.piece(), other.piece()
        return Circuit(a.parts + b.parts, a.left + b.left, a.right + b.right)

    def __or__(self, other: Circuit) -> Circuit:
        return Spider(1, 2) >> (self @ other) >> Spider(2, 1)

    def __invert__(self) -> Circuit:
        return Spider(0, 2) >> (self @ Spider(1, 1)) >> Spider(2, 0)

    def __neg__(self) -> Circuit:
        wire = Spider(1, 1)
        return (wire @ Spider(0, 2)) >> (wire @ self @ wire) >> (Spider(2, 0) @ wire)

    @property
    def free(self) -> tuple[int, int]:
        """How many of its ends, left and right, are not on a named point."""
        return sum(not isinstance(p, Node) for p in self.left), sum(not isinstance(p, Node) for p in self.right)

    # What it means

    def closed(self, leak: float = 0.0) -> Laws:
        """A closed circuit's laws; ``leak``: a tiny conductance from every point to ground."""
        if self.free != (0, 0):
            raise NotClosed(*self.free)
        return self.laws_except((), leak)

    def laws_except(self, ends: tuple[Point, ...], leak: float = 0.0) -> Laws:
        """Each element's laws on the potentials of its points, and Kirchhoff at every point except ``ends``
        (where current comes in from outside)."""
        at = {e.V[t]: p.potential for e, t, p in self.ends() if e.V[t] != p.potential}
        own = Laws(
            tuple(q for e in self.members for q in e.equations), tuple(e.ways for e in self.members if e.ways), at
        )
        own = own.map(lambda x: x.xreplace(at))
        return Laws(own.equations + self._kirchhoff(leak, ends), own.ways, at)

    def _kirchhoff(self, leak: float, ends: tuple[Point, ...]) -> tuple[Equation, ...]:
        """At every point but ground and ``ends``: what flows into the elements there adds up to nothing."""
        into: dict[Point, list[sp.Expr]] = {}
        for e, t, p in self.ends():
            into.setdefault(p, []).append(e.I[t])
        return tuple(
            Equation(sp.Add(*currents) + leak * p.potential, Origin("kcl", p))
            for p, currents in into.items()
            if p.potential != 0 and p not in ends
        )

    def __str__(self) -> str:
        """A 1 → 1 piece's law at its ends, as a book writes it: ``U = I·(R_1 + R_2)``."""
        from .solve import law

        return law(self)

    def final(self, values: Mapping | None = None, frame=None):
        """Where the circuit settles: DC, or AC with sines of one frequency."""
        from .solve import final

        return final(self, values or {}, frame)

    def simulate(self, values: Mapping | None = None, until: float = 1.0, dt: float | None = None, inputs=None):
        """Frame after frame from rest, for ``until`` seconds."""
        from .simulate import simulate

        return simulate(self, values or {}, until, dt, inputs)


def _same(pairs) -> dict[Point, Point]:
    """For each point, the one it becomes when every pair is made one point; a named point stays."""
    one: dict[Point, Point] = {}

    def find(p: Point) -> Point:
        while p in one:
            p = one[p]
        return p

    for x, y in pairs:
        x, y = find(x), find(y)
        if x == y:
            continue
        if isinstance(x, Node) and isinstance(y, Node):
            raise JoinsNodes(x, y)
        keep, drop = (y, x) if isinstance(y, Node) else (x, y)
        one[drop] = keep
    return {p: find(p) for p in one}


class Node(Point, Circuit):
    """A named point (1 → 1): the same object wherever it is used is the same point; ``label`` is only shown."""

    def __init__(self, label: str | None = None, potential: sp.Expr | None = None) -> None:
        if label is not None and not re.fullmatch(r"\w+", label):
            raise BadName(label)
        self.label = label
        Point.__init__(self, potential if potential is not None else sp.Dummy(f"V_{label or ''}"))
        Circuit.__init__(self, (), (self,), (self,))

    def __repr__(self) -> str:
        return f"Node({self.label!r})"


class Net(Node):
    """A point every ``Net`` of the same name is: ``GND`` (potential 0), ``VCC``."""

    def __init__(self, name: str) -> None:
        super().__init__(name, sp.Integer(0) if name == "GND" else sp.Symbol(f"V_{name}"))

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Net) and other.label == self.label

    def __hash__(self) -> int:
        return hash(("Net", self.label))

    def __repr__(self) -> str:
        return f"Net({self.label!r})"


class Spider(Circuit):
    """``dom`` ends on the left and ``cod`` on the right, all on one point."""

    def __init__(self, dom: int, cod: int) -> None:
        p = Point()
        super().__init__((), (p,) * dom, (p,) * cod)


class Swap(Circuit):
    """Two ends crossing (2 → 2)."""

    def __init__(self) -> None:
        a, b = Point(), Point()
        super().__init__((), (a, b), (b, a))


GND = Net("GND")
wire = Spider(1, 1)
cap = Spider(0, 2)
cup = Spider(2, 0)
swap = Swap()


def labels(c: Circuit) -> dict[Element, str]:
    """Each element's label: its name when no other element has it; else its prefix and a number in order
    (``R_1``, ``R_2``), skipping names already taken (``R1`` takes ``R_1`` too)."""
    names = [e.name for e in c.members]
    unique = {x for x in names if x and names.count(x) == 1}
    taken = {x.replace("_", "") for x in unique}
    counters: Counter[str] = Counter()

    def numbered(prefix: str) -> str:
        while True:
            counters[prefix] += 1
            label = f"{prefix}_{counters[prefix]}"
            if label.replace("_", "") not in taken:
                taken.add(label.replace("_", ""))
                return label

    return {e: e.name if e.name in unique else numbered(e.prefix) for e in c.members}


def points(c: Circuit) -> list[Point]:
    """Its points, in the order they are first met."""
    return list(dict.fromkeys(p for _, _, p in c.ends()))
