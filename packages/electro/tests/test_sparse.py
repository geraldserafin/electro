"""The sparse elimination (``sparse.shape``, ``engine.System``) solves what plain elimination does: on random
sparse systems, part of their entries changing from step to step, the part kept between steps too, and a
pivot that comes out nothing here (it then falls back to partial pivoting); switches' rows left to the block,
each switch either way."""

import random

import pytest
from electro.numeric.engine import System, solve_linear
from electro.numeric.sparse import shape


def _system(n: int, seed: int):
    rng = random.Random(seed)
    entries = sorted({(i, i) for i in range(n)} | {(rng.randrange(n), rng.randrange(n)) for _ in range(2 * n)})
    dynamic = [rng.random() < 0.3 for _ in entries]
    values = [rng.uniform(1, 3) * (5 if i == j else 1) * rng.choice((-1, 1)) for i, j in entries]
    return entries, dynamic, values


def _dense(n, entries, values, b):
    J = [0.0] * (n * n)
    for (i, j), v in zip(entries, values):
        J[i * n + j] += v
    b = list(b)
    return b if solve_linear(J, b, n) else None


@pytest.mark.parametrize("seed", range(20))
def test_sparse_solves_as_dense(seed):
    n = 3 + seed % 9
    entries, dynamic, values = _system(n, seed)
    now = list(values)

    def jconst(p, A):
        for k, d in enumerate(dynamic):
            if not d:
                A[k] = now[k]

    def jdyn(x, p, F, A):
        for i in range(n):
            F[i] = -float(i + 1)  # the step solves J·dx = (1, 2, …)
        for k, d in enumerate(dynamic):
            if d:
                A[k] = now[k] * (1 + x[0])

    system = System(shape(n, entries, values, dynamic), jconst, jdyn)
    for x0 in (0.0, 0.5, -0.25):  # the moving part changes, the kept one stays
        system.begin([])
        assert system.step([x0] + [0.0] * (n - 1), [])
        scaled = [v * (1 + x0) if d else v for v, d in zip(now, dynamic)]
        assert system.dx == pytest.approx(_dense(n, entries, scaled, range(1, n + 1)), rel=1e-9, abs=1e-12)
    for k in range(len(entries)):  # pivots gone, one by one (open switches); the kept part eliminated again
        now[k] = 0.0
        expected = _dense(n, entries, now, range(1, n + 1))
        system.begin([])
        assert system.step([0.0] * n, []) == (expected is not None)
        if expected is not None:
            assert system.dx == pytest.approx(expected, rel=1e-6, abs=1e-9)


@pytest.mark.parametrize("seed", range(10))
def test_switches_rows_solve_either_way(seed):
    """A ladder of nodes to ground, every other link a switch: closed, no voltage across it; open, no current
    through it. The plan is made with them all open; the block takes every combination."""
    rng = random.Random(seed)
    k = 2 + seed % 4  # switches
    nodes = k + 1  # node i: unknown i; switch s: its current, unknown nodes + s, its law row nodes + s
    n = nodes + k
    g = [rng.uniform(0.5, 2) for _ in range(nodes)]

    def matrix(closed):
        cells = {}
        for i in range(nodes):  # KCL: g_i·V_i (to ground) + the switches' currents in and out
            cells[i, i] = g[i]
        for s in range(k):
            a, b, row, cur = s, s + 1, nodes + s, nodes + s
            cells[a, cur], cells[b, cur] = 1.0, -1.0
            if closed[s]:
                cells[row, a], cells[row, b], cells[row, cur] = 1.0, -1.0, 0.0
            else:
                cells[row, a], cells[row, b], cells[row, cur] = 0.0, 0.0, 1.0
        return sorted(cells), cells

    entries, open_cells = matrix([False] * k)
    now = [open_cells[c] for c in entries]
    plan = shape(n, entries, now, [False] * len(entries), switched=range(nodes, n))
    system = System(plan, jconst_of(now), jdyn_of(n))
    assert system.k2 == n - k
    system.solve_dense = None  # (never: the block takes every way the switches are)
    for combo in range(2**k):
        closed = [bool(combo >> s & 1) for s in range(k)]
        _, cells = matrix(closed)
        now[:] = [cells[c] for c in entries]
        system.begin([])
        assert system.step([0.0] * n, [])
        assert system.dx == pytest.approx(_dense(n, entries, now, range(1, n + 1)), rel=1e-9, abs=1e-12)


def jconst_of(now):
    def jconst(p, A):
        for i, v in enumerate(now):
            A[i] = v

    return jconst


def jdyn_of(n):
    def jdyn(x, p, F, A):
        for i in range(n):
            F[i] = -float(i + 1)

    return jdyn
