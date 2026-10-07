"""The code view of a schematic cell edited back: the code (written by the page, ``schematic/code.ts``,
then by the user) run, the circuit it makes, with its values, as drawing data for the page to lay out."""

from __future__ import annotations

import json
import re

from electro import Circuit

from .drawing import to_drawing
from .errors import CELL, NoCircuitInCode, error

PRELUDE = "from electro import *\nfrom electro_notebook.methods import fill, resistance, swept"


def variable(name: str) -> str:
    """A schematic's name as the Python variable cells see it: ``"Układ 1"`` → ``układ1``."""
    v = re.sub(r"\W", "", name.lower())
    if not v:
        return "uklad"
    return f"_{v}" if v[0].isdigit() else v


def from_code(source: str, name: str) -> str:
    """``source`` run: its circuit (the variable called like the schematic, else the last closed one it makes)
    and its values (``<variable>_values``, else none). JSON ``{"netlist": {...}}`` or ``{"error": {...}}``."""
    var = variable(name)
    scope: dict = {}
    exec(PRELUDE, scope)
    prelude = set(scope)
    try:
        exec(compile(source, CELL, "exec"), scope)
        circuit = _circuit_in(scope, var, prelude)
        return json.dumps({"netlist": to_drawing(circuit, scope.get(f"{var}_values") or {})}, ensure_ascii=False)
    except Exception as err:  # noqa: BLE001 — any mistake in the code is shown to the user
        return json.dumps({"error": error(err)}, ensure_ascii=False)


def _circuit_in(scope: dict, var: str, prelude: set) -> Circuit:
    """The circuit called ``var``, else the last closed circuit the code made."""
    if isinstance(scope.get(var), Circuit):
        return scope[var]
    made = [
        v for k, v in scope.items() if k not in prelude and isinstance(v, Circuit) and v.members and v.free == (0, 0)
    ]
    if not made:
        raise NoCircuitInCode(variable=var)
    return made[-1]
