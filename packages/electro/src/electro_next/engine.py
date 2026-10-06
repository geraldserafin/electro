"""The engine every frame runs on: numbers only, no algebra — plain Python, so that the page can get it as
JavaScript printed from this very file. Newton's method on a frame's equations (compiled from its formula:
``code``), the sources raised from nothing when nothing came before, a p-n junction approached along its
exponential as SPICE does, and a linear system solved by elimination.

A kernel is ``kernel(x, p, F, J)``: it fills ``F`` with the equations' values at the unknowns ``x`` and the
parameters ``p``, ``J`` (zeroed first) with their derivatives, n × n row by row.
"""

import math

RELTOL = 1e-6
VNTOL = 1e-6
MAX_NEWTON = 60
EXP_LIMIT = 80.0


def newton(kernel, x0, p, junctions):
    """A root near ``x0``, or None; ``junctions``: each one's unknown, the scale it moves on, where it bends."""
    n = len(x0)
    x = list(x0)
    F = [0.0] * n
    J = [0.0] * (n * n)
    for iteration in range(1, MAX_NEWTON + 1):
        for k in range(n * n):
            J[k] = 0.0
        try:
            kernel(x, p, F, J)
        except OverflowError:
            return None
        dx = solve_linear(J, [-f for f in F], n)
        if dx is None:
            return None
        new = [x[k] + dx[k] for k in range(n)]
        if any(math.isnan(v) for v in new):
            return None
        for i, nvt, vcrit in junctions:
            new[i] = junction_step(new[i], x[i], nvt, vcrit)
        done = all(abs(new[k] - x[k]) <= RELTOL * max(abs(new[k]), abs(x[k])) + VNTOL for k in range(n))
        x = new
        if done and iteration > 1:
            return x
    return None


def homotopy(find, n):
    """A root at λ = 1 of what ``find(x0, λ)`` finds near ``x0``, the sources raised from λ = 0, where
    everything is zero. Each raise starts where the last ended; a raise Newton does not finish is halved."""
    x = find([0.0] * n, 0.0)
    lam = 0.0
    raise_by = 0.25
    while x is not None and lam < 1:
        to = min(1.0, lam + raise_by)
        found = find(x, to)
        if found is None:
            raise_by = raise_by / 2
            if raise_by < 1e-6:
                return None
            continue
        x = found
        lam = to
        raise_by = min(1.0, raise_by * 2)
    return x


def junction_step(new, old, nvt, vcrit):
    """SPICE's: along the exponential, never far past its bend in one go."""
    if new > vcrit and abs(new - old) > 2 * nvt:
        if old > 0:
            arg = 1 + (new - old) / nvt
            return old + nvt * math.log(arg) if arg > 0 else vcrit
        return nvt * math.log(new / nvt)
    return new


def solve_linear(A, b, n):
    """``A·x = b`` (``A`` flat, row by row) by elimination with partial pivoting, each row scaled to its
    largest entry first, so laws in volts and in amperes pivot alike. None: singular."""
    M = []
    for i in range(n):
        row = [A[i * n + j] for j in range(n)]
        row.append(b[i])
        big = max(abs(v) for v in row[:n]) if n else 1.0
        if big == 0:
            big = 1.0
        M.append([v / big for v in row])
    for col in range(n):
        pivot = col
        for r in range(col + 1, n):
            if abs(M[r][col]) > abs(M[pivot][col]):
                pivot = r
        if abs(M[pivot][col]) < 1e-300:
            return None
        M[col], M[pivot] = M[pivot], M[col]
        inv = 1.0 / M[col][col]
        for r in range(col + 1, n):
            f = M[r][col] * inv
            if f != 0:
                for c in range(col, n + 1):
                    M[r][c] -= f * M[col][c]
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        s = M[i][n]
        for j in range(i + 1, n):
            s -= M[i][j] * x[j]
        x[i] = s / M[i][i]
    return x


def limited_exp(x):
    """``exp``, continued along its tangent beyond ``EXP_LIMIT``: Newton's first guesses never overflow."""
    return math.exp(x) if x <= EXP_LIMIT else math.exp(EXP_LIMIT) * (1 + x - EXP_LIMIT)


def limited_exp_slope(x):
    return math.exp(min(x, EXP_LIMIT))
