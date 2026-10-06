"""The sparse elimination (``sparse.shape``, ``engine.System``) solves what plain elimination does: on random
sparse systems, part of their entries changing from step to step, the part kept between steps too, and a
pivot that comes out nothing here (it then falls back to partial pivoting)."""

import random

import pytest
from electro.engine import System, solve_linear
from electro.sparse import shape


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
