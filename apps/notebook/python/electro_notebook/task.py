"""A circuit to solve, its answer checked but not shown: ``task(circuit, values, "I_R_1", "Find the current…")``.

The answer is kept only as hashes of where it falls on a logarithmic scale with steps of ``tol`` (and the
two steps beside it), so a reader's value within about ``tol`` of it is right (``cells/task.ts`` checks it),
and the note — its file too — does not give it away. A check, for learning; not a lock (the circuit is there
to be solved by anyone who runs it)."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping
from dataclasses import dataclass

import sympy as sp
from electro import Element
from electro.quantities import Quantity

from .latex import name
from .names import named, names
from .results import shown

LETTERS = {"I": "A", "U": "V", "V": "V", "P": "W"}


def _bucket(value: float, tol: float) -> int:
    return round(math.log(abs(value)) / math.log1p(tol))


def _hash(quantity: str, bucket: str) -> str:
    return hashlib.sha256(f"{quantity}|{bucket}".encode()).hexdigest()


def hashes(quantity: str, value: float, tol: float) -> tuple[str, ...]:
    if abs(value) < 1e-15:
        return (_hash(quantity, "0"),)
    sign, k = "-" if value < 0 else "+", _bucket(value, tol)
    return tuple(_hash(quantity, f"{sign}{k + d}") for d in (-1, 0, 1))


@dataclass(frozen=True)
class Task:
    prompt: str
    quantity: str  # what is asked, by name: "I_R_1"
    unit: str
    tol: float
    hashes: tuple[str, ...]
    amplitude: bool = False  # an AC quantity: its amplitude is asked

    def _output_(self) -> dict:
        return {
            "type": "task",
            "prompt": self.prompt,
            "quantity": self.quantity,
            "tex": name(self.quantity),
            "unit": self.unit,
            "tol": self.tol,
            "hashes": list(self.hashes),
            "amplitude": self.amplitude,
        }


def task(
    circuit: Element,
    values: Mapping,
    find: str | Quantity,
    prompt: str = "",
    *,
    tol: float = 0.01,
    units: Mapping[str, str] = {},
) -> Task:
    """Find ``find`` (``"I_R_1"``, ``"R_2"``, ``"V_A"``, or the quantity) in ``circuit``, its ``values`` in;
    the notebook shows ``prompt`` and a field to answer in, checked within ``tol`` (1 %). ``units``: each
    kind's value's."""
    from .cells import _name

    n = names(circuit)
    elements = {label: e for e, label in n.labels.items()}
    quantity, label = (named(find, n), find) if isinstance(find, str) else (find, _name(find, circuit))
    value = complex(sp.N(shown(circuit.final(values), quantity)))
    amplitude = abs(value.imag) > 1e-12 * max(1.0, abs(value))
    number = abs(value) if amplitude else value.real
    letter = label.partition("_")[0]
    unit = units.get(elements[label].kind, "") if label in elements else LETTERS.get(letter, "")
    return Task(prompt, label, unit, tol, hashes(label, number, tol), amplitude)
