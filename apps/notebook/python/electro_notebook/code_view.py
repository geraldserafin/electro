"""The code view of a schematic cell edited back: the code (written by the page, ``schematic/code.ts``,
then by the user) run, the circuit it makes, with its values, as drawing data for the page to lay out."""

from __future__ import annotations

import json
import re

from electro import Element

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
    """``source`` run, its circuit (the variable called like the schematic, else the last one it makes) and
    its values (``<variable>_values``, else none). Returns JSON ``{"netlist": {...}}`` or ``{"error": {...}}``."""
    var = variable(name)
    scope: dict = {}
    exec(PRELUDE, scope)
    prelude = set(scope)
    try:
        exec(compile(source, CELL, "exec"), scope)
        found = scope.get(var)
        if not isinstance(found, Element):
            made = [
                v
                for k, v in scope.items()
                if k not in prelude and isinstance(v, Element) and v.members and v.free == (0, 0)
            ]
            if not made:
                raise NoCircuitInCode(variable=var)
            found = made[-1]
        values = scope.get(f"{var}_values") or {}
        return json.dumps({"netlist": to_drawing(found, values)}, ensure_ascii=False)
    except Exception as err:  # noqa: BLE001 — any mistake in the code is shown to the user
        return json.dumps({"error": error(err)}, ensure_ascii=False)
