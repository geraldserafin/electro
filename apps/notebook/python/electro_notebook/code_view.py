"""The code view of a schematic cell: its drawing as electro code, and the code edited back as the problem it
makes (netlist data, and the series and parallel it is made of, for the page to lay out)."""

from __future__ import annotations

import json
import re

from electro import Circuit, Problem, to_netlist
from electro.code.structure import shape, to_data
from electro.code.write import code as written
from electro.problem.netlist import from_netlist

from .errors import CELL, NoCircuitInCode, error

PRELUDE = "from electro import *"


def variable(name: str) -> str:
    """A schematic's name as the Python variable cells see it: ``"Układ 1"`` → ``układ1``."""
    v = re.sub(r"\W", "", name.lower())
    if not v:
        return "uklad"
    return f"_{v}" if v[0].isdigit() else v


def code(problem_json: str, name: str) -> str:
    """A drawing (its problem, ``schematic/problem.ts``) as electro code."""
    return written(from_netlist(json.loads(problem_json)).problem, variable(name))


def from_code(source: str, name: str) -> str:
    """``source`` run, its problem (the variable called like the schematic, else the last one it makes; a
    circuit alone is a problem with no data). Returns JSON ``{"netlist": {...}, "shape": {...} | null}`` or
    ``{"error": {...}}``."""
    var = variable(name)
    scope: dict = {}
    exec(PRELUDE, scope)
    prelude = set(scope)
    try:
        exec(compile(source, CELL, "exec"), scope)
        found = scope.get(var)
        if not isinstance(found, Problem | Circuit):
            made = [v for k, v in scope.items() if k not in prelude and isinstance(v, Problem | Circuit)]
            if not made:
                raise NoCircuitInCode(variable=var)
            found = made[-1]
        problem = found if isinstance(found, Problem) else Problem(found)
        laid = shape(problem)
        data = {"netlist": to_netlist(problem), "shape": to_data(laid) if laid is not None else None}
        return json.dumps(data, ensure_ascii=False)
    except Exception as err:  # noqa: BLE001 — any mistake in the code is shown to the user
        return json.dumps({"error": error(err)}, ensure_ascii=False)
