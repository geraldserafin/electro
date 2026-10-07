"""How a sparse Jacobian is eliminated, chosen once when a frame's equations are compiled (``code``); the
engine (``engine.System``) only follows it, never touching an entry that stays zero.

Each pivot is the entry that makes the fewest new nonzeros (Markowitz, as SPICE does), among those not much
smaller than the largest left in their column (in a sample frame's numbers: a pivot near zero is none). First
come pivots whose row and column the unknowns never change: that part of the elimination is the same in every
Newton step, so the engine does it once while those entries stay the same."""

from __future__ import annotations

import math
from collections.abc import Sequence

THRESHOLD = 0.1
"""A pivot is at least this fraction of the largest entry left in its column."""

Cell = tuple[int, int]


class Elimination:
    """A sample Jacobian as it is eliminated: each entry's value, whether the unknowns change it, and its place
    in the engine's array ``A`` (new entries go after the given ones)."""

    def __init__(self, n: int, entries: Sequence[Cell], sample: Sequence[float], dynamic: Sequence[bool]) -> None:
        self.n, self.m = n, len(entries)
        self.value: dict[Cell, float] = {}
        self.moving: dict[Cell, bool] = {}
        self.place: dict[Cell, int] = {}
        for k, (cell, v, d) in enumerate(zip(entries, sample, dynamic)):
            self.value[cell] = self.value.get(cell, 0.0) + (v if math.isfinite(v) else 1e30)
            self.moving[cell] = self.moving.get(cell, False) or d
            self.place.setdefault(cell, k)
        self.rows, self.cols = set(range(n)), set(range(n))
        self.in_row: dict[int, set[int]] = {i: {j for r, j in self.value if r == i} for i in range(n)}
        self.in_col: dict[int, set[int]] = {j: {i for i, c in self.value if c == j} for j in range(n)}

    def below(self, c: int) -> list[int]:
        """The rows left with an entry in column ``c``."""
        return sorted(i for i in self.in_col[c] if i in self.rows)

    def right(self, r: int) -> list[int]:
        """The columns left with an entry in row ``r``."""
        return sorted(j for j in self.in_row[r] if j in self.cols)

    def fixed(self, r: int, c: int) -> bool:
        """Whether no entry in the pivot's row or column changes with the unknowns."""
        return not any(self.moving[r, j] for j in self.right(r)) and not any(self.moving[i, c] for i in self.below(c))

    def pivot(self, fixed_first: bool) -> tuple[int, int, bool]:
        """The next pivot: big enough, then (when ``fixed_first``) one the unknowns never change, then the fewest
        new entries, then the biggest."""
        best = None
        for c in self.cols:
            rows = self.below(c)
            top = max((abs(self.value[i, c]) for i in rows), default=0.0)
            for r in rows:
                if top > 0 and abs(self.value[r, c]) < THRESHOLD * top:
                    continue
                fixed = self.fixed(r, c)
                cost = (len(self.right(r)) - 1) * (len(rows) - 1)
                key = (fixed_first and not fixed, cost, -abs(self.value[r, c]) / (top or 1.0), r, c)
                if best is None or key < best[0]:
                    best = (key, r, c, fixed)
        if best is None:
            raise ValueError("a structurally singular Jacobian")
        return best[1], best[2], best[3]

    def eliminate(self, r: int, c: int) -> tuple[list[Cell], list[Cell], list[int]]:
        """Pivot ``(r, c)`` taken: the entries below it, the entries it updates, and the columns right of it."""
        below, right = [i for i in self.below(c) if i != r], [j for j in self.right(r) if j != c]
        updates = []
        for i in below:
            factor = self.value[i, c] / self.value[r, c] if self.value[r, c] else 0.0
            for j in right:
                self._entry(i, j)
                self.value[i, j] -= factor * self.value[r, j]
                self.moving[i, j] = self.moving[i, j] or self.moving[i, c] or self.moving[r, j]
                updates.append((i, j))
        self.rows.discard(r)
        self.cols.discard(c)
        return [(i, c) for i in below], updates, right

    def _entry(self, i: int, j: int) -> None:
        """A new nonzero (fill-in), at the end of ``A``."""
        if (i, j) not in self.value:
            self.value[i, j], self.moving[i, j], self.place[i, j] = 0.0, False, self.m
            self.m += 1
            self.in_row[i].add(j)
            self.in_col[j].add(i)


def shape(n: int, entries: Sequence[Cell], sample: Sequence[float], dynamic: Sequence[bool]) -> dict:
    """The elimination as the engine reads it. ``entries``: each nonzero's (row, column), in ``A``'s order;
    ``sample``: their values in a sample frame; ``dynamic``: which the unknowns change."""
    a = Elimination(n, entries, sample, dynamic)
    order, steps, k1 = [], [], n
    for _ in range(n):
        r, c, fixed = a.pivot(fixed_first=k1 == n)
        if k1 == n and not fixed:
            k1 = len(order)
        order.append((r, c))
        steps.append(a.eliminate(r, c))
    return _for_engine(a, order, steps, k1, entries, dynamic)


def _for_engine(a: Elimination, order: list[Cell], steps: list, k1: int, entries: Sequence[Cell], dynamic) -> dict:
    """The plan as flat arrays of places in ``A``, as the engine (printed as JavaScript) reads it: for each pivot
    the entries below it (``low``), the updates it makes (``upd``: target, below, right, and whether it falls on
    the part the unknowns change while the pivot is in the first ``k1``), and the entries right of it (``up``)."""
    head_rows, head_cols = {r for r, _ in order[:k1]}, {c for _, c in order[:k1]}

    def trailing(i: int, j: int) -> bool:
        return i not in head_rows and j not in head_cols

    out: dict = {"n": a.n, "m": a.m, "k1": k1, "linear": not any(dynamic)}
    out |= {"rows": [i for i, _ in entries], "cols": [j for _, j in entries]}
    out |= {"constant": [k for k, d in enumerate(dynamic) if not d]}
    out |= {"pivots": [a.place[cell] for cell in order], "prow": [r for r, _ in order], "pcol": [c for _, c in order]}
    out |= {"low": [], "low_row": [], "low_at": [0], "upd": [], "upd_at": [0], "up": [], "up_col": [], "up_at": [0]}
    for k, ((r, c), (lows, updates, right)) in enumerate(zip(order, steps)):
        out["low"] += [a.place[cell] for cell in lows]
        out["low_row"] += [i for i, _ in lows]
        out["low_at"].append(len(out["low"]))
        for i, j in updates:
            out["upd"] += [a.place[i, j], a.place[i, c], a.place[r, j], 1 if k < k1 and trailing(i, j) else 0]
        out["upd_at"].append(len(out["upd"]))
        out["up"] += [a.place[r, j] for j in right]
        out["up_col"] += right
        out["up_at"].append(len(out["up"]))
    out["head"] = sorted(a.place[cell] for cell in a.place if not trailing(*cell))
    out["trail"] = sorted(a.place[cell] for cell in a.place if trailing(*cell))
    return out
