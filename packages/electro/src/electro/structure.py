"""The order a system of equations is solved in, read off which unknowns each equation holds (the structural
analysis equation-based modelling makes, as Modelica's compilers do): each equation matched to an unknown it
gives (a maximum matching), then the blocks that must be solved together (strongly connected — Tarjan),
each after those it needs. A block of one is one equation giving one unknown; a bigger one, equations together.

What no matching reaches splits off (Dulmage–Mendelsohn): unknowns no equation is left for — the data
missing — and equations no unknown is left for — they must hold of what the rest found, or the data clash."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import sympy as sp

Block = tuple[tuple[int, ...], tuple[sp.Symbol, ...]]
"""Equations' places, and the unknowns they give."""


@dataclass(frozen=True)
class Structure:
    """``blocks`` in order; ``over``: the block of equations more than their unknowns (some say again what
    others do — Kirchhoff all round a loop — or they clash), solved first, all together; ``under``: the block
    of equations holding unknowns no equation is left for (``free``: the data missing), solved last, in them."""

    blocks: tuple[Block, ...]
    over: Block
    under: Block
    free: tuple[sp.Symbol, ...]


def structure(holds: Sequence[set[sp.Symbol]]) -> Structure:
    """``holds``: the unknowns each equation holds."""
    n = len(holds)
    xs = sorted({x for h in holds for x in h}, key=str)
    of: dict[sp.Symbol, list[int]] = {x: [i for i in range(n) if x in holds[i]] for x in xs}
    gives: dict[int, sp.Symbol] = {}
    given_by: dict[sp.Symbol, int] = {}

    def augment(i: int, seen: set[sp.Symbol]) -> bool:
        for x in sorted(holds[i], key=str):
            if x not in seen:
                seen.add(x)
                if x not in given_by or augment(given_by[x], seen):
                    gives[i], given_by[x] = x, i
                    return True
        return False

    for i in range(n):
        augment(i, set())
    over = _reach([i for i in range(n) if i not in gives], lambda i: [given_by[x] for x in holds[i] if x in given_by])
    unmatched = [x for x in xs if x not in given_by]
    undetermined = _reach(unmatched, lambda x: [gives[i] for i in of[x] if i in gives])
    under = {given_by[x] for x in undetermined if x in given_by}
    square = [i for i in gives if i not in over and i not in under]
    needs = {i: [given_by[x] for x in holds[i] if given_by[x] != i and given_by[x] in square] for i in square}
    blocks = tuple((tuple(b), tuple(gives[i] for i in b)) for b in _components(square, needs))

    def block(places) -> Block:
        places = sorted(places)
        return tuple(places), tuple(gives[i] for i in places if i in gives)

    return Structure(blocks, block(over), block(under), tuple(unmatched))


def _reach(start, step) -> set:
    seen, todo = set(start), list(start)
    while todo:
        for nxt in step(todo.pop()):
            if nxt not in seen:
                seen.add(nxt)
                todo.append(nxt)
    return seen


def _components(nodes: list[int], needs: dict[int, list[int]]) -> list[list[int]]:
    """Strongly connected components (Tarjan), each after those it needs."""
    index: dict[int, int] = {}
    low: dict[int, int] = {}
    stack: list[int] = []
    on: set[int] = set()
    out: list[list[int]] = []

    def visit(v: int) -> None:
        index[v] = low[v] = len(index)
        stack.append(v)
        on.add(v)
        for w in needs[v]:
            if w not in index:
                visit(w)
                low[v] = min(low[v], low[w])
            elif w in on:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            block = []
            while True:
                w = stack.pop()
                on.discard(w)
                block.append(w)
                if w == v:
                    break
            out.append(sorted(block))

    for v in nodes:
        if v not in index:
            visit(v)
    return out
