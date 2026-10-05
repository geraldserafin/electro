"""What a circuit is made of, as a book draws it: series and parallel, found by the classic reduction — two
elements between the same two points are one in parallel, a point where exactly two meet (and nothing is
named) joins them in series. A circuit that does not reduce to one loop or to branches between two points (a
bridge, an op-amp) has none."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from ..circuit.netlist import labels
from ..circuit.tree import netlist
from ..problem.netlist import point_names
from ..problem.problem import Problem
from ..solver.laws import is_source

SYMMETRIC = ("resistor", "capacitor", "inductor")
"""Kinds the same either way round (only their arrows' signs change)."""

AUTO = re.compile(r"(.+_)?n\d+")
"""The names a drawing gives points it does not name."""


@dataclass(frozen=True)
class Leaf:
    index: int
    id: str
    kind: str
    flipped: bool = False

    def reversed(self) -> Leaf:
        return Leaf(self.index, self.id, self.kind, not self.flipped)

    def leaves(self) -> list[Leaf]:
        return [self]


@dataclass(frozen=True)
class Named:
    """A named point inside a series chain."""

    name: str

    def reversed(self) -> Named:
        return self

    def leaves(self) -> list[Leaf]:
        return []


@dataclass(frozen=True)
class Series:
    parts: tuple[Tree, ...]

    def reversed(self) -> Series:
        return Series(tuple(p.reversed() for p in reversed(self.parts)))

    def leaves(self) -> list[Leaf]:
        return [leaf for p in self.parts for leaf in p.leaves()]


@dataclass(frozen=True)
class Parallel:
    parts: tuple[Tree, ...]

    def reversed(self) -> Parallel:
        return Parallel(tuple(p.reversed() for p in self.parts))

    def leaves(self) -> list[Leaf]:
        return [leaf for p in self.parts for leaf in p.leaves()]


Tree = Leaf | Named | Series | Parallel


@dataclass(frozen=True)
class Loop:
    """Everything in one loop, from a source round."""

    parts: tuple[Tree, ...]


@dataclass(frozen=True)
class Between:
    """A piece between two points: branches several of which have a source (as drawn for superposition),
    or a network between two named points (a divider between its terminals)."""

    tree: Tree
    a: str
    b: str


Shape = Loop | Between


def series_of(*parts: Tree) -> Series:
    return Series(tuple(q for p in parts for q in (p.parts if isinstance(p, Series) else (p,))))


def parallel_of(*parts: Tree) -> Parallel:
    flat = [q for p in parts for q in (p.parts if isinstance(p, Parallel) else (p,))]
    return Parallel(tuple(sorted(flat, key=lambda p: min(leaf.index for leaf in p.leaves()))))


def shape(problem: Problem) -> Shape | None:
    net = netlist(problem.circuit)
    if any(len(ns) != 2 for _, ns in net.parts):
        return None
    names = point_names(net)
    named = {n for n in names if n != "GND" and not AUTO.fullmatch(n)}
    ids = labels(net)
    sources = {k for k, (e, _) in enumerate(net.parts) if is_source(e)}
    edges: list[tuple[Tree, str, str]] = [
        (Leaf(k, ids[k], e.kind.name), names[a], names[b]) for k, (e, (a, b)) in enumerate(net.parts)
    ]
    while _parallel_step(edges) or _series_step(edges, named):
        pass
    if len(edges) != 1:
        return None
    tree, u, v = edges[0]
    if isinstance(tree, Parallel):
        with_source = [p for p in tree.parts if _has(p, sources)]
        if len(with_source) > 1:
            return Between(tree, u, v)
        first = with_source[0] if with_source else tree.parts[0]
        rest = [p for p in tree.parts if p is not first]
        load = rest[0] if len(rest) == 1 else parallel_of(*rest)
        ends = [[Named(n)] if n in named else [] for n in (u, v)]
        tree, v = series_of(*ends[0], first, *ends[1], load.reversed()), u
    if u != v:
        return Between(tree, u, v)
    tree = _nicest(tree)
    parts = tree.parts if isinstance(tree, Series) else (tree,)
    start = next((i for i, p in enumerate(parts) if isinstance(p, Leaf) and p.index in sources), 0)
    return Loop(parts[start:] + parts[:start])


def to_data(s: Shape) -> dict:
    """For the page's layout: ``{"loop": [...]}`` or ``{"between": part, "a": …, "b": …}``; each part
    ``{"element": id, "flip": …}``, ``{"node": name}``, ``{"series": [...]}``, ``{"parallel": [...]}``."""
    match s:
        case Loop(parts):
            return {"loop": [_tree_data(p) for p in parts]}
        case Between(tree, a, b):
            return {"between": _tree_data(tree), "a": a, "b": b}
    raise TypeError(s)


def _tree_data(t: Tree) -> dict:
    match t:
        case Leaf(_, id, kind, flipped):
            return {"element": id, "flip": flipped and kind not in SYMMETRIC}
        case Named(name):
            return {"node": name}
        case Series(parts):
            return {"series": [_tree_data(p) for p in parts]}
        case Parallel(parts):
            return {"parallel": [_tree_data(p) for p in parts]}
    raise TypeError(t)


def _has(t: Tree, sources: set[int]) -> bool:
    return any(leaf.index in sources for leaf in t.leaves())


def _against(t: Tree) -> int:
    """How many direction-sensitive elements a reading direction turns round."""
    return sum(1 for leaf in t.leaves() if leaf.flipped and leaf.kind not in SYMMETRIC)


def _nicest(t: Tree) -> Tree:
    """The way round that turns fewer elements."""
    flipped = t.reversed()
    return flipped if _against(flipped) < _against(t) else t


def _series_step(edges: list[tuple[Tree, str, str]], named: set[str]) -> bool:
    """The two elements at a point where exactly two ends meet, joined (the smallest first, ground last)."""
    degree: dict[str, list[int]] = {}
    for i, (_, u, v) in enumerate(edges):
        degree.setdefault(u, []).append(i)
        degree.setdefault(v, []).append(i)
    candidates = [(n, inc) for n, inc in degree.items() if len(inc) == 2 and inc[0] != inc[1]]
    candidates.sort(key=lambda c: (c[0] == "GND", sum(len(edges[i][0].leaves()) for i in c[1])))
    for n, incident in candidates[:1]:
        (e1, a1, b1), (e2, a2, b2) = edges[incident[0]], edges[incident[1]]
        first, x = (e1, a1) if b1 == n else (e1.reversed(), b1)
        second, y = (e2, b2) if a2 == n else (e2.reversed(), a2)
        middle: Sequence[Tree] = [Named(n)] if n in named else []
        for i in sorted(incident, reverse=True):
            del edges[i]
        edges.append((series_of(first, *middle, second), x, y))
        return True
    return False


def _parallel_step(edges: list[tuple[Tree, str, str]]) -> bool:
    """Two between the same two (distinct) points, joined."""
    seen: dict[frozenset, int] = {}
    for i, (t, u, v) in enumerate(edges):
        if u == v:
            continue
        pair = frozenset((u, v))
        if pair in seen:
            j = seen[pair]
            f, a, b = edges[j]
            edges[j] = (parallel_of(f, t if (u, v) == (a, b) else t.reversed()), a, b)
            del edges[i]
            return True
        seen[pair] = i
    return False
