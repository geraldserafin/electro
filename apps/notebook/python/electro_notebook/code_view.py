"""The code view of a schematic cell edited back: the code (written by the page, ``schematic/code.ts``,
then by the user) run, the circuit it makes, with its values, as drawing data for the page to lay out."""

from __future__ import annotations

import ast
import json
import re

from electro import Circuit

from .drawing import to_drawing
from .errors import CELL, NoCircuitInCode, error

PRELUDE = (
    "from electro import *\n"
    "from electro_notebook.methods import Resistance, Thevenin, fill, resistance, swept, thevenin"
)


def variable(name: str) -> str:
    """A schematic's name as the Python variable cells see it: ``"Układ 1"`` → ``układ1``."""
    v = re.sub(r"\W", "", name.lower())
    if not v:
        return "uklad"
    return f"_{v}" if v[0].isdigit() else v


FINAL = "__final__"
"""Where the circuit's ``final`` call stands in what the code shows (``show``)."""


def from_code(source: str, name: str) -> str:
    """``source`` run up to its circuit (the variable called like the schematic, else the last closed one it
    makes); what follows is what the code shows, not run here: ``show``, its ``final`` call ``__final__``
    (``steps(__final__)``; none when that call is all of it), the values that call is given (else
    ``<variable>_values``, else none). JSON ``{"netlist": {...}, "show": str | None}`` or ``{"error": {...}}``."""
    var = variable(name)
    scope: dict = {}
    exec(PRELUDE, scope)
    prelude = set(scope)
    try:
        tree = ast.parse(source, CELL)
        head, tail = _split(tree.body, var)
        exec(compile(ast.Module(head, []), CELL, "exec"), scope)
        call = _final_call(tail)
        circuit = _eval(call.func.value, scope) if call else None  # type: ignore[attr-defined]
        if not isinstance(circuit, Circuit):
            circuit = _circuit_in(scope, var, prelude)
        values = _eval(call.args[0], scope) if call and call.args else scope.get(f"{var}_values") or {}
        show = _show(source, tail, call)
        return json.dumps({"netlist": to_drawing(circuit, values), "show": show}, ensure_ascii=False)
    except Exception as err:  # noqa: BLE001 — any mistake in the code is shown to the user
        return json.dumps({"error": error(err)}, ensure_ascii=False)


def _split(body: list[ast.stmt], var: str) -> tuple[list[ast.stmt], list[ast.stmt]]:
    """The code up to its circuit, and what follows: after the last ``var = …`` (but ``<var>_values = …``,
    as the page wrote values before); with none, the last line when it solves."""
    made = [i for i, s in enumerate(body) if isinstance(s, ast.Assign) and _names(s.targets) == [var]]
    if made:
        head, tail = body[: made[-1] + 1], body[made[-1] + 1 :]
        values = [s for s in tail if isinstance(s, ast.Assign) and _names(s.targets) == [f"{var}_values"]]
        return head + values, [s for s in tail if s not in values]
    if body and _final_call(body[-1:]):
        return body[:-1], body[-1:]
    return body, []


def _names(targets: list[ast.expr]) -> list[str]:
    return [t.id for t in targets if isinstance(t, ast.Name)]


def _final_call(tail: list[ast.stmt]) -> ast.Call | None:
    """The first ``….final(…)`` in ``tail``."""
    calls = (n for s in tail for n in ast.walk(s) if isinstance(n, ast.Call))
    return next((c for c in calls if isinstance(c.func, ast.Attribute) and c.func.attr == "final"), None)


def _show(source: str, tail: list[ast.stmt], call: ast.Call | None) -> str | None:
    """``tail`` as written, its ``final`` call ``__final__``; None when it is that call alone, or nothing."""
    if not tail:
        return None
    text = "\n".join(source.splitlines()[tail[0].lineno - 1 :]).strip()
    if call is not None:
        text = text.replace(ast.get_source_segment(source, call) or FINAL, FINAL, 1)
    return None if text == FINAL else text


def _eval(node: ast.expr, scope: dict):
    return eval(compile(ast.Expression(node), CELL, "eval"), scope)


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
