"""Plain numbers: a linear system, solved by elimination."""

from __future__ import annotations


def solve_linear(A: list[float], b: list[float], n: int) -> list[float] | None:
    """``A·x = b`` (``A`` flat, row by row) by Gaussian elimination with partial pivoting; each row scaled
    to its largest entry first, so laws in volts and in amperes pivot alike. None: singular."""
    M = [_scaled(A[i * n : (i + 1) * n] + [b[i]], n) for i in range(n)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(M[r][col]))
        if abs(M[pivot][col]) < 1e-300:
            return None
        M[col], M[pivot] = M[pivot], M[col]
        _eliminate_below(M, col, n)
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        x[i] = (M[i][n] - sum(M[i][j] * x[j] for j in range(i + 1, n))) / M[i][i]
    return x


def _scaled(row: list[float], n: int) -> list[float]:
    big = max(abs(v) for v in row[:n]) or 1.0
    return [v / big for v in row]


def _eliminate_below(M: list[list[float]], col: int, n: int) -> None:
    row = M[col]
    inv = 1.0 / row[col]
    for r in range(col + 1, n):
        f = M[r][col] * inv
        if f:
            Mr = M[r]
            for c in range(col, n + 1):
                Mr[c] -= f * row[c]
