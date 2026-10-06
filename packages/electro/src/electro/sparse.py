"""How a sparse Jacobian is eliminated, chosen once, when a frame's equations are compiled (``code``); the
engine (``engine.System``) then only follows it, touching no entry that stays zero.

Each step takes as pivot the entry that makes the fewest new ones (Markowitz, as SPICE does), among those
not much smaller than the largest in their column (the numbers of a sample frame: a pivot near nothing is
no pivot), first among those whose row and column the unknowns never change: that part of the elimination
is the same from one Newton step to the next, and is done once while those entries stay the same.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

THRESHOLD = 0.1
"""A pivot is at least this fraction of the largest entry left in its column (of the sample)."""


def shape(n: int, entries: Sequence[tuple[int, int]], sample: Sequence[float], dynamic: Sequence[bool]) -> dict:
    """``entries``: each nonzero's (row, column), in ``A``'s order; ``sample``: their values in a sample
    frame; ``dynamic``: which the unknowns change. The elimination as the engine reads it."""
    value: dict[tuple[int, int], float] = {}
    moving: dict[tuple[int, int], bool] = {}
    position: dict[tuple[int, int], int] = {}
    for k, (rc, v, d) in enumerate(zip(entries, sample, dynamic)):
        value[rc] = value.get(rc, 0.0) + (v if math.isfinite(v) else 1e30)
        moving[rc] = moving.get(rc, False) or d
        position.setdefault(rc, k)
    m = len(entries)
    rows_left, cols_left = set(range(n)), set(range(n))
    in_row: dict[int, set[int]] = {i: set() for i in range(n)}
    in_col: dict[int, set[int]] = {j: set() for j in range(n)}
    for i, j in value:
        in_row[i].add(j)
        in_col[j].add(i)
    order: list[tuple[int, int]] = []
    steps: list[tuple[list[tuple[int, int]], list[tuple[int, int]], list[int]]] = []
    k1 = n
    for _ in range(n):
        best = None
        for j in cols_left:
            below = [i for i in in_col[j] if i in rows_left]
            top = max((abs(value[i, j]) for i in below), default=0.0)
            for i in below:
                if top > 0 and abs(value[i, j]) < THRESHOLD * top:
                    continue
                fixed = not any(moving[i, c] for c in in_row[i] if c in cols_left) and not any(
                    moving[r, j] for r in below
                )
                cost = (len(in_row[i] & cols_left) - 1) * (len(below) - 1)
                key = (not (k1 == n and fixed), cost, -abs(value[i, j]) / (top or 1.0), i, j)
                if best is None or key < best[0]:
                    best = (key, i, j, fixed)
        if best is None:
            raise ValueError("a structurally singular Jacobian")
        _, r, c, fixed = best
        if k1 == n and not fixed:
            k1 = len(order)
        order.append((r, c))
        below = sorted(i for i in in_col[c] if i in rows_left and i != r)
        right = sorted(j for j in in_row[r] if j in cols_left and j != c)
        updates = []
        for i in below:
            factor = value[i, c] / value[r, c] if value[r, c] else 0.0
            for j in right:
                if (i, j) not in value:
                    value[i, j], moving[i, j], position[i, j] = 0.0, False, m
                    m += 1
                    in_row[i].add(j)
                    in_col[j].add(i)
                value[i, j] -= factor * value[r, j]
                moving[i, j] = moving[i, j] or moving[i, c] or moving[r, j]
                updates.append((i, j))
        steps.append(([(i, c) for i in below], updates, right))
        rows_left.discard(r)
        cols_left.discard(c)
    head_rows = {r for r, _ in order[:k1]}
    head_cols = {c for _, c in order[:k1]}
    out: dict = {"n": n, "m": m, "k1": k1, "linear": not any(dynamic)}
    out["rows"] = [i for i, _ in entries]
    out["cols"] = [j for _, j in entries]
    out["constant"] = [k for k, d in enumerate(dynamic) if not d]
    out["pivots"] = [position[rc] for rc in order]
    out["prow"] = [r for r, _ in order]
    out["pcol"] = [c for _, c in order]
    out["low"], out["low_row"], out["low_at"] = [], [], [0]
    out["upd"], out["upd_at"] = [], [0]
    out["up"], out["up_col"], out["up_at"] = [], [], [0]
    for k, ((r, c), (lows, updates, right)) in enumerate(zip(order, steps)):
        out["low"] += [position[rc] for rc in lows]
        out["low_row"] += [i for i, _ in lows]
        out["low_at"].append(len(out["low"]))
        for i, j in updates:
            trailing = i not in head_rows and j not in head_cols
            out["upd"] += [position[i, j], position[i, c], position[r, j], 1 if k < k1 and trailing else 0]
        out["upd_at"].append(len(out["upd"]))
        out["up"] += [position[r, j] for j in right]
        out["up_col"] += right
        out["up_at"].append(len(out["up"]))
    out["head"] = sorted(position[i, j] for i, j in position if i in head_rows or j in head_cols)
    out["trail"] = sorted(position[i, j] for i, j in position if i not in head_rows and j not in head_cols)
    return out
