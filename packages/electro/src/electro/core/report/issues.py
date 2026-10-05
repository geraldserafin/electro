"""What went wrong, as data: its type's name and its fields, quantities and values in LaTeX — whoever shows
it says it in the reader's language (``shared/model/issues.ts``)."""

from __future__ import annotations

from collections.abc import Mapping

import sympy as sp

from ..circuit.tree import Element
from ..problem.problem import Problem
from ..problem.quantities import Quantity
from ..solver.errors import Ambiguous, Contradiction, MissingData
from ..solver.symbols import symbols
from . import tex


def issue(err: BaseException, problem: Problem | None = None, units: Mapping[str, str] | None = None) -> dict | None:
    """``err`` as data, or None when it is not one of electro's. ``units``: each element's value's."""
    units = units or {}
    if problem is not None:
        s = symbols(problem.circuit)
        match err:
            case MissingData():
                return {
                    "type": "MissingData",
                    "targets": [tex.quantity(q, s) for q in err.targets],
                    "needed": err.needed,
                    "options": [[tex.quantity(q, s)] for q in err.options],
                }
            case Contradiction():
                return _clash(err, problem, units)
            case Ambiguous():
                return {
                    "type": "Ambiguous",
                    "options": [[_equals(x, v, units.get(x.name, "")) for x, v in o.items()] for o in err.options],
                }
    if type(err).__module__.startswith("electro.core") and vars(err):
        return {"type": type(err).__name__, **{k: _field(k, v) for k, v in vars(err).items()}}
    return None


def _clash(err: Contradiction, problem: Problem, units: Mapping[str, str]) -> dict:
    """The data that clash: conditions on quantities, and elements' values."""
    s = symbols(problem.circuit)
    conditions, values = [], []
    for key in err.data:
        given = problem.given[key]
        if isinstance(key, Element):
            label = s.labels[s.index(key)]
            values.append(_equals(sp.Symbol(label), given, units.get(label, "")))
        elif isinstance(key, Quantity):
            conditions.append(f"{tex.quantity(key, s)} = {tex.value(given, tex.unit(key, units, s))}")
    return {"type": "ConflictingData", "conditions": conditions, "values": values}


def _equals(x: sp.Symbol, v: object, unit: str) -> str:
    return f"{tex.name(x.name)} = {tex.value(v, unit)}"


def _field(key: str, v: object) -> object:
    return tex.name(v) if key == "label" and isinstance(v, str) else v
