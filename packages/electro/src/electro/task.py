"""A problem to solve, with its answer checked but not shown: ``task(c, "I_R_1", "Find the current…")``.

The answer is kept only as hashes of where it falls on a logarithmic scale with steps of ``tol``
(and the two steps beside it), so a reader's value within about ``tol`` of it is right, and the
note — its file too — does not give it away. A check, for learning; not a lock (the circuit is
there to be solved by anyone who runs it).
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass

import sympy as sp

from .circuit import Circuit
from .values import parse


def _bucket(value: float, tol: float) -> str:
    if abs(value) < 1e-15:
        return "0"
    return f"{'-' if value < 0 else '+'}{round(math.log(abs(value)) / math.log1p(tol))}"


def _hash(quantity: str, bucket: str) -> str:
    return hashlib.sha256(f"{quantity}|{bucket}".encode()).hexdigest()


def _hashes(quantity: str, value: float, tol: float) -> tuple[str, ...]:
    if abs(value) < 1e-15:
        return (_hash(quantity, "0"),)
    sign, k = _bucket(value, tol)[0], int(_bucket(value, tol)[1:])
    return tuple(_hash(quantity, f"{sign}{k + d}") for d in (-1, 0, 1))


@dataclass(frozen=True)
class Task:
    prompt: str
    quantity: str  # what is asked, as the solver names it: "I_R_1"
    unit: str
    tol: float
    hashes: tuple[str, ...]
    amplitude: bool = False  # an AC quantity: its amplitude is asked

    def check(self, answer) -> bool:
        """Is ``answer`` (a number or ``"25 mA"``) right, within about ``tol``?"""
        value = complex(parse(answer) if isinstance(answer, str) else answer)
        value = abs(value) if self.amplitude else value.real
        if abs(value) < 1e-15:
            return _hash(self.quantity, "0") in self.hashes
        return _hash(self.quantity, _bucket(value, self.tol)) in self.hashes

    def __repr__(self):
        return f"{self.prompt}\n{self.quantity} = ? {self.unit}"


def task(c: Circuit, find: str, prompt: str | None = None, *, tol: float = 0.01, omega=None, **given) -> Task:
    """A problem on ``c``: find ``find`` (``"I_R_1"``, ``"R_2"``, ``"V_A"``) from ``given``; the
    notebook shows ``prompt`` and a field to answer in, checked within ``tol`` (1 %)."""
    sol = c.solve(omega=omega, find=find, **given)
    symbol = sol.find[0]
    value = complex(sp.N(sol.answers[symbol.name]))
    amplitude = abs(value.imag) > 1e-12 * max(1.0, abs(value))
    number = abs(value) if amplitude else value.real
    unit = sol.unit(symbol)
    return Task(prompt or "", symbol.name, unit, tol, _hashes(symbol.name, number, tol), amplitude)
