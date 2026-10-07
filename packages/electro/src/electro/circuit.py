"""A circuit is a drawing: elements, and the points their terminals are on, and its free ends — the
morphisms of the free hypergraph category (cospans of hypergraphs). Joining only says which points are one:

- ``f >> g``: ``f``'s right ends are ``g``'s left ends — their points made one (a pushout);
- ``f @ g``: side by side;
- ``f | g``, ``~f``, ``-f``: ``>>`` and ``@`` with points (``Spider``: one point, any ends).

Nothing is solved by joining. What a circuit means comes out only when it is asked: its laws (``closed``: each
element's on the potentials of its points, Kirchhoff at every point), then a frame of them (``solve``,
``simulate``)."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

import sympy as sp

from .errors import BadName, ElementTwice, JoinsNodes, NotClosed, WrongEnds

if TYPE_CHECKING:
    from .element import Element, Equation, Way


class Point:
    """Where ends meet. Its potential: one variable for all that touch it."""

    def __init__(self, potential: sp.Expr | None = None) -> None:
        self.potential = potential if potential is not None else sp.Dummy("v")

    def __repr__(self) -> str:
        return f"Point({self.potential})"


Parts = tuple[tuple["Element", tuple[Point, ...]], ...]


class Circuit:
    """Elements on points (``parts``: each element and the points of its drawn terminals, in order), with
    ``left`` and ``right`` ends: the points the rest joins it at."""

    parts: Parts
    left: tuple[Point, ...]
    right: tuple[Point, ...]

    def __init__(self, parts: Parts = (), left: tuple[Point, ...] = (), right: tuple[Point, ...] = ()) -> None:
        self.parts, self.left, self.right = parts, left, right
        elements = [e for e, _ in parts]
        if len({id(e) for e in elements}) != len(elements):
            raise ElementTwice(next(e for e in elements if elements.count(e) > 1).name or "an element")

    @property
    def members(self) -> tuple[Element, ...]:
        return tuple(e for e, _ in self.parts)

    def piece(self) -> Circuit:
        """As it is used: an element is one object, in one place; points with no element on them (a spider,
        what is made of them) are fresh wherever they are used."""
        if self.parts:
            return self
        fresh: dict[Point, Point] = {}

        def new(p: Point) -> Point:
            return p if isinstance(p, Node) else fresh.setdefault(p, Point())

        return Circuit((), tuple(map(new, self.left)), tuple(map(new, self.right)))

    # Joining

    def __rshift__(self, other: Circuit) -> Circuit:
        a, b = self.piece(), other.piece()
        if len(a.right) != len(b.left):
            raise WrongEnds(len(a.right), len(b.left))
        one: dict[Point, Point] = {}

        def find(p: Point) -> Point:
            while p in one:
                p = one[p]
            return p

        for x, y in zip(a.right, b.left):
            x, y = find(x), find(y)
            if x == y:
                continue
            if isinstance(x, Node) and isinstance(y, Node):
                raise JoinsNodes(x, y)
            x, y = (y, x) if isinstance(y, Node) else (x, y)
            one[y] = x
        parts = tuple((e, tuple(map(find, ps))) for e, ps in a.parts + b.parts)
        return Circuit(parts, tuple(map(find, a.left)), tuple(map(find, b.right)))

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
        """How many of its ends, left and right, are not on a named point: still to be joined."""
        return sum(not isinstance(p, Node) for p in self.left), sum(not isinstance(p, Node) for p in self.right)

    # What it means

    def closed(self, leak: float = 0.0) -> Laws:
        """A closed circuit's laws: each element's on the potentials of its points, Kirchhoff at every point
        (``leak``: a whisper of a conductance from each to ground)."""
        if self.free != (0, 0):
            raise NotClosed(*self.free)
        return _laws(self, leak)

    def __str__(self) -> str:
        """A 1 → 1 piece as a book writes it, ``U = I·(R_1 + R_2)``: its laws seen at its ends (its voltage
        ``U``, the first end against the second; its current ``I``, in at the first), all else hidden."""
        from .solve import law

        return law(self)

    def final(self, values: Mapping | None = None, frame=None):
        """Where the circuit comes to: one frame infinitely long — or, with sines of one frequency, turning at
        it — from rest, its values in."""
        from .solve import final

        return final(self, values or {}, frame)

    def simulate(self, values: Mapping | None = None, until: float = 1.0, dt: float | None = None, inputs=None):
        """Frame after frame from rest for ``until`` seconds."""
        from .simulate import simulate

        return simulate(self, values or {}, until, dt, inputs)


class Node(Point, Circuit):
    """A named point (1 → 1): the same object wherever it is used is one point; ``label`` only shows."""

    def __init__(self, label: str | None = None, potential: sp.Expr | None = None) -> None:
        if label is not None and not re.fullmatch(r"\w+", label):
            raise BadName(label)
        self.label = label
        Point.__init__(self, potential if potential is not None else sp.Dummy(f"V_{label or ''}"))
        Circuit.__init__(self, (), (self,), (self,))

    def __repr__(self) -> str:
        return f"Node({self.label!r})"


class Net(Node):
    """A point every ``Net`` of that name is: ``GND`` (potential 0), ``VCC``."""

    def __init__(self, name: str) -> None:
        super().__init__(name, sp.Integer(0) if name == "GND" else sp.Symbol(f"V_{name}"))

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Net) and other.label == self.label

    def __hash__(self) -> int:
        return hash(("Net", self.label))

    def __repr__(self) -> str:
        return f"Net({self.label!r})"


class Spider(Circuit):
    """``dom`` ends in on the left and ``cod`` out on the right, all on one point."""

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


# Its laws


@dataclass(frozen=True)
class Laws:
    """A closed circuit's laws: ``equations``; ``ways``, each element of several its ways (one of each holds);
    ``at``: each element's terminal potential as its point's."""

    equations: tuple[Equation, ...]
    ways: tuple[tuple[Way, ...], ...]
    at: Mapping[sp.Symbol, sp.Expr]

    def map(self, f) -> Laws:
        """Every expression through ``f`` (a frame's reading, values put in)."""
        from .element import Equation, Way

        def eq(q: Equation) -> Equation:
            return Equation(f(q.expr), q.origin)

        ways = tuple(
            tuple(Way(w.element, w.name, tuple(map(eq, w.equations)), tuple(map(f, w.holds))) for w in c)
            for c in self.ways
        )
        return Laws(tuple(map(eq, self.equations)), ways, self.at)

    def expressions(self) -> list[sp.Expr]:
        out = [q.expr for q in self.equations]
        return out + [e for c in self.ways for w in c for e in (*(q.expr for q in w.equations), *w.holds)]


def _laws(c: Circuit, leak: float, ends: tuple[Point, ...] = ()) -> Laws:
    """``c``'s laws; Kirchhoff at every point but ``ends`` (there current comes in from outside)."""
    from .element import Equation, Origin

    at = {e.V[t]: p.potential for e, ps in c.parts for t, p in zip(e.drawn, ps) if e.V[t] != p.potential}

    def put(x: sp.Expr) -> sp.Expr:
        return x.xreplace(at)

    laws = Laws(tuple(q for e in c.members for q in e.equations), tuple(e.ways for e in c.members if e.ways), at)
    laws = laws.map(put)
    into: dict[Point, list[sp.Expr]] = {}
    for e, ps in c.parts:
        for t, p in zip(e.drawn, ps):
            into.setdefault(p, []).append(e.I[t])
    kcl = tuple(
        Equation(sp.Add(*currents) + leak * p.potential, Origin("kcl", p))
        for p, currents in into.items()
        if p.potential != 0 and p not in ends
    )
    return Laws(laws.equations + kcl, laws.ways, at)


def labels(c: Circuit) -> dict[Element, str]:
    """Each element's label: its name when no other has it; the others numbered by their prefix in order
    (``R_1``, ``R_2``), past the names taken (``R1`` takes ``R_1`` too)."""
    named = [e.name for e in c.members]
    unique = {x for x in named if x and named.count(x) == 1}
    taken = {x.replace("_", "") for x in unique}
    counters: Counter[str] = Counter()
    out = {}
    for e in c.members:
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


def points(c: Circuit) -> list[Point]:
    """Its points, in the order they are first met."""
    return list(dict.fromkeys(p for _, ps in c.parts for p in ps))
