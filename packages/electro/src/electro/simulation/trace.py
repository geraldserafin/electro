"""What happened in a run: the time of each step and every quantity then."""

from __future__ import annotations

import cmath
import math
from array import array
from dataclasses import dataclass

import sympy as sp

from ..problem.problem import Problem
from ..problem.quantities import Quantity, Scaled
from ..solver.step import StepFunction
from ..solver.symbols import symbols


@dataclass
class Trace:
    """``data``: each step's unknowns one after another (8 bytes a number: a long run of a big circuit
    would take several times more as lists of floats, and Pyodide's memory never shrinks back)."""

    problem: Problem
    phi: StepFunction
    t: list[float]
    data: array

    def __call__(self, q: Quantity | Scaled | str) -> list[float]:
        """``q`` at each step: a quantity, or an unknown's or a point's name (``"I_R_1"``, ``"V_A"``)."""
        if isinstance(q, str):
            return self._column(q)
        e = symbols(self.problem.circuit).of(q)
        names = sorted({s.name for s in e.free_symbols if isinstance(s, sp.Symbol)})
        f = sp.lambdify([sp.Symbol(n) for n in names], e, "math")
        columns = [self._column(n) for n in names]
        return [float(f(*row)) for row in zip(*columns)] if names else [float(e)] * len(self.t)

    def at(self, q: Quantity | Scaled | str, t: float) -> float:
        """``q`` at the last step not after ``t``."""
        k = max((i for i, s in enumerate(self.t) if s <= t + 1e-15), default=0)
        return self(q)[k]

    def spectrum(self, q: Quantity | Scaled | str, points: int = 4096, f_max: float | None = None):
        """``q``'s amplitude at each frequency (the trace resampled evenly, a Hann window): a sine of 5 V at 50 Hz
        is a peak of 5 at 50. Up to ``f_max`` Hz (by default a quarter of the sampling rate). Returns the
        frequencies and the amplitudes."""
        t0, t1 = self.t[0], self.t[-1]
        n = 1 << max(3, (points - 1).bit_length())
        dt = (t1 - t0) / n
        window = [0.5 - 0.5 * math.cos(2 * math.pi * k / n) for k in range(n)]
        keep = n // 4 if f_max is None else min(n // 2, int(f_max * dt * n) + 1)
        samples = _resample(self.t, self(q), [t0 + k * dt for k in range(n)])
        mean = sum(samples) / n
        spectrum = _fft([(v - mean) * w for v, w in zip(samples, window)])
        gain = 2 / sum(window)
        return [k / (dt * n) for k in range(keep)], [abs(mean)] + [abs(x) * gain for x in spectrum[1:keep]]

    def _column(self, name: str) -> list[float]:
        if name in self.phi.unknowns:
            return self.data[self.phi.unknowns.index(name) :: len(self.phi.unknowns)].tolist()
        node = self.phi.nodes.get(name[2:]) if name.startswith("V_") else None
        if node is not None:
            return self._column(self.phi.unknowns[node])
        if name.startswith("V_") and name[2:] in self.phi.nodes:
            return [0.0] * len(self.t)
        raise KeyError(name)


def _resample(t: list[float], y: list[float], at: list[float]) -> list[float]:
    """``y(t)`` at the times ``at`` (increasing), straight between the steps."""
    out, i = [], 0
    for s in at:
        while i + 1 < len(t) - 1 and t[i + 1] <= s:
            i += 1
        j = min(i + 1, len(t) - 1)
        f = 0.0 if t[j] == t[i] else min(max((s - t[i]) / (t[j] - t[i]), 0.0), 1.0)
        out.append(y[i] + f * (y[j] - y[i]))
    return out


def _fft(x: list[float]) -> list[complex]:
    """Radix-2 (``len(x)`` a power of two), iterative: no numpy in the notebook."""
    n = len(x)
    a = [complex(v) for v in x]
    j = 0
    for i in range(1, n):
        bit = n >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j |= bit
        if i < j:
            a[i], a[j] = a[j], a[i]
    size = 2
    while size <= n:
        w = cmath.exp(-2j * math.pi / size)
        for start in range(0, n, size):
            wk = 1
            for k in range(size // 2):
                u, v = a[start + k], a[start + k + size // 2] * wk
                a[start + k], a[start + k + size // 2] = u + v, u - v
                wk *= w
        size <<= 1
    return a
