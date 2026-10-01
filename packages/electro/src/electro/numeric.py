"""A linear circuit solved in numbers, many times over: a frequency sweep, a parameter sweep.

``LinearSystem(c, ctx, params)`` compiles the circuit once into a sparse system ``A·x = b`` whose
coefficients are functions of ``params`` (``omega``, a component's value); ``solve(*values)`` then
fills it in and eliminates, with no sympy on the way. The step-by-step solver stays for what is
read by people; this is for the hundreds of points a plot needs.
"""

from __future__ import annotations

import sympy as sp
from sympy.solvers.solveset import NonlinearError

from .circuit import Circuit
from .components import Context
from .issues import NoSystemSolution, NotLinear, Undetermined
from .semantics import compile_circuit
from .solver import _resolve
from .values import expression


class LinearSystem:
    def __init__(self, c: Circuit, ctx: Context = Context(), params: tuple[sp.Symbol, ...] = ()):  # noqa: B008
        self.params = tuple(params)
        self.system = system = compile_circuit(c, ctx=ctx, unknowns_as_symbols=True)
        self.known = {k: v for k, v in system.known.items() if k not in self.params}
        # readings (an ammeter's value) are outputs here, not data: the quantity they read is asked instead
        exprs = [law.expr.xreplace(self.known) for law in system.laws if law.kind != "reading"]
        self.unknowns = [u for u in system.unknowns if u not in self.params]
        stray = set().union(*(e.free_symbols for e in exprs)) - set(self.unknowns) - set(self.params)
        if stray:
            raise Undetermined(sorted(stray, key=lambda s: s.name))
        try:
            A, b = sp.linear_eq_to_matrix(exprs, self.unknowns)
        except NonlinearError as err:
            raise NotLinear() from err
        cells, coeffs = [], []  # cells[i]: (column, index into coeffs) per nonzero; then b's index
        for i in range(A.rows):
            row = []
            for j in range(A.cols):
                if A[i, j] != 0:
                    row.append((j, len(coeffs)))
                    coeffs.append(A[i, j])
            cells.append((row, len(coeffs)))
            coeffs.append(b[i])
        self._cells = cells
        self._coeffs = sp.lambdify(self.params, coeffs, "math")

    def solve(self, *values) -> dict[sp.Symbol, complex]:
        """Every unknown's value for these values of ``params``."""
        numbers = [complex(v) for v in self._coeffs(*values)]
        rows = [{j: numbers[k] for j, k in row} for row, _ in self._cells]
        rhs = [numbers[k] for _, k in self._cells]
        x = _eliminate(rows, rhs, len(self.unknowns))
        return dict(zip(self.unknowns, x))

    def value(self, expr, x: dict[sp.Symbol, complex], values=()) -> complex:
        """A quantity (``"V_A"``, ``"I_R_1"``, ``"U_C_1 / E_1"``) at a solution ``x`` from ``solve``."""
        e = _resolve(expression(expr), self.system) if isinstance(expr, str) else expr
        e = e.xreplace(dict(zip(self.params, values))).xreplace(self.known).xreplace(x)
        return complex(e)


def _eliminate(rows: list[dict[int, complex]], rhs: list[complex], n: int) -> list[complex]:
    """Sparse Gaussian elimination: each time the shortest row left (little fill-in), on its largest
    entry. Raises ``NoSystemSolution`` for no solution, ``Undetermined`` for more than one."""
    where: dict[int, set[int]] = {j: set() for j in range(n)}  # column -> rows (left) that have it
    for i, row in enumerate(rows):
        for j in row:
            where[j].add(i)
    left, order = set(range(len(rows))), []
    scale = max((abs(v) for row in rows for v in row.values()), default=1.0)
    while left:
        i = min(left, key=lambda r: len(rows[r]))
        left.discard(i)
        row = rows[i]
        if not row:
            if abs(rhs[i]) > 1e-9 * max(scale, 1.0):
                raise NoSystemSolution([])
            continue
        j = max(row, key=lambda k: abs(row[k]))
        p = row[j]
        for r in where[j] - {i}:
            if r not in left:
                continue
            f = rows[r].pop(j) / p
            where[j].discard(r)
            for k, v in row.items():
                if k == j:
                    continue
                new = rows[r].get(k, 0) - f * v
                if new == 0:
                    rows[r].pop(k, None)
                    where[k].discard(r)
                else:
                    rows[r][k] = new
                    where[k].add(r)
            rhs[r] -= f * rhs[i]
        order.append((i, j))
    if len(order) < n:
        raise Undetermined([])
    x = [0j] * n
    for i, j in reversed(order):
        row = rows[i]
        x[j] = (rhs[i] - sum(v * x[k] for k, v in row.items() if k != j)) / row[j]
    return x
