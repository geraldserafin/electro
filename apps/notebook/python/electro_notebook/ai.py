"""The AI's ``solve`` tool: quantities of a drawing, by name, as its board would show them."""

from __future__ import annotations

import json

import sympy as sp

from .drawing import from_drawing
from .errors import error
from .names import expression, named, names
from .results import amplitude, shown, solved


def task_values(problem_json: str, steps_json: str) -> str:
    """Each step's ``value`` (a quantity's name or an expression of them, ``U_E_1 / I_E_1``) on a drawing's
    problem. Returns JSON ``{"values": {step: {"value": x} | {"error": ...}}}`` (an AC one as its amplitude)
    or ``{"error": {...}}`` (the circuit)."""
    try:
        net = from_drawing(json.loads(problem_json))
        solution, _ = solved(net.circuit, net.values, net.elements)
    except Exception as err:  # noqa: BLE001 — said to the AI
        return json.dumps({"error": error(err)}, ensure_ascii=False)
    values: dict[str, dict] = {}
    for step in json.loads(steps_json):
        try:
            e = expression(step["value"])
            value = e.subs({s: shown(solution, named(s.name, names(solution.circuit))) for s in e.free_symbols})
            values[step["id"]] = {"value": amplitude(sp.N(value))}
        except Exception as err:  # noqa: BLE001 — said by the step that has it
            values[step["id"]] = {"error": error(err)}
    return json.dumps({"values": values}, ensure_ascii=False)
