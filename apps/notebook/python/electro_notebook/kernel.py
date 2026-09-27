"""Notebook kernel: runs cells in one shared namespace and turns results into outputs.

Every cell sees what earlier cells defined, like in Jupyter. The value of the last
expression is shown; objects with ``_repr_svg_`` / ``_repr_markdown_`` show as a
picture / formatted text. Schematic cells are available as ``schemat("name")``.
"""

from __future__ import annotations

import ast
import contextlib
import io
import json
import traceback
import warnings

from electro import CircuitError
from sympy import I as sp_I
from electro_render import symbol_library
from electro_schematic import Schematic

CELL = "<komórka>"
PRELUDE = """
from electro import *
from electro_render import schematic, steps
from electro_schematic import Schematic, layout
"""

namespace: dict = {}


def reset() -> None:
    """Forget everything the cells defined."""
    namespace.clear()
    exec(PRELUDE, namespace)


def symbols() -> str:
    return json.dumps(symbol_library(), ensure_ascii=False)


def code(schematic_json: str, name: str) -> str:
    """A drawing as plain electro code, for the "show code" button."""
    variable = name if name.isidentifier() else "uklad"
    return Schematic.from_json(schematic_json).to_code(variable)


def from_code(source: str, name: str, old_json: str = "") -> str:
    """The code view edited back into a drawing: run ``source`` and lay out its circuit.

    The circuit is the variable called like the schematic (``uklad``), else the last one the
    code defines. When only values changed, the old drawing (``old_json``) keeps its layout
    with the new values; otherwise the circuit is laid out anew.
    Returns JSON ``{"schematic": ...}`` or ``{"error": "..."}``.
    """
    from electro import Circuit
    from electro_schematic import layout
    from electro_schematic.layout import Unsupported

    variable = name if name.isidentifier() else "uklad"
    scope: dict = {}
    exec(PRELUDE, scope)
    prelude = set(scope)
    try:
        exec(compile(source, CELL, "exec"), scope)
        found = scope.get(variable)
        if not isinstance(found, Circuit):
            defined = [v for k, v in scope.items() if k not in prelude and isinstance(v, Circuit)]
            if not defined:
                raise ValueError(f"W kodzie nie ma układu — przypisz go do zmiennej, np. {variable} = loop(...)")
            found = defined[-1]
        kept = _same_but_values(Schematic.from_json(old_json), found, variable) if old_json else None
        if kept is not None:
            return json.dumps({"schematic": json.loads(kept.to_json())}, ensure_ascii=False)
        try:
            fresh = layout(found)
        except Unsupported as err:
            raise ValueError(f"{err} Tu zmieniaj w kodzie tylko wartości, a elementy dodawaj na schemacie.") from None
        return json.dumps({"schematic": json.loads(fresh.to_json())}, ensure_ascii=False)
    except Exception as err:  # noqa: BLE001 — any mistake in the code is shown to the user
        return json.dumps({"error": _error(err)}, ensure_ascii=False)


def _same_but_values(old: Schematic, circuit, variable: str) -> Schematic | None:
    """``old`` with the values from ``circuit``, if that makes it the same circuit (else None)."""
    from electro.codegen import code
    from electro.semantics import compile_circuit
    from electro.values import UNKNOWN, to_text

    parts = compile_circuit(circuit).parts
    ids = {e.id for e in old.elements}
    if not set(parts) <= ids:
        return None
    for e in old.elements:
        if e.id in parts:
            c = parts[e.id].component
            e.value = to_text(c.value) if c.has_value and c.value is not UNKNOWN else None
    try:
        return old if old.to_code(variable) == code(circuit, variable) else None
    except Exception:  # noqa: BLE001 — an unfinished old drawing: lay out the new circuit instead
        return None


def _parse_data(text: str) -> dict[str, str]:
    """``"I_R_1 = 0,5; U_R_2 = 4"`` (``;`` or new lines between entries) → keyword arguments for solve()."""
    given = {}
    for entry in text.replace("\n", ";").split(";"):
        if not entry.strip():
            continue
        name, sep, value = entry.partition("=")
        if not sep or not name.strip() or not value.strip():
            raise ValueError(f"Nie rozumiem „{entry.strip()}” — wpisz np. I_R_1 = 0,5")
        given[name.strip()] = value.strip()
    return given


def simulate(schematic_json: str, data: str = "") -> str:
    """The "Symuluj" button: solve a drawing and report every element's values.

    Returns JSON ``{"results": {id: {...}}, "outputs": [...]}``; ``results`` go next to the
    elements on the canvas, ``outputs`` (a table, warnings, errors) under the drawing.
    """
    from electro.values import UNKNOWN, fmt
    from electro_render.schematic import _short
    from electro_render.trace import name as latex_name

    sch = Schematic.from_json(schematic_json)
    outputs: list[dict] = []
    results: dict[str, dict] = {}
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            solution = sch.to_circuit().solve(**_parse_data(data))
        except (CircuitError, ValueError, KeyError) as err:
            message = err.args[0] if isinstance(err, KeyError) and err.args else err
            return json.dumps({"results": {}, "outputs": [{"type": "error", "data": str(message)}]}, ensure_ascii=False)
    rows = ["| element | wartość | U | I | P |", "|---|---|---|---|---|"]
    for label in solution.system.parts:
        r = solution[label]
        comp = r.component
        current = r.I if r.I is not None and r.I.is_real and r.I.is_number else None
        sign = -1 if current is not None and current < 0 else 1
        if r.realized is not None:
            value = _short(r.realized)
        elif comp.has_value:
            value = fmt(r.value, comp.unit) if r.value is not None else "?"
        else:
            value = ""
        entry = {
            "value": value,
            "solved": (comp.has_value and comp.value is UNKNOWN and r.value is not None) or r.realized is not None,
            "U": fmt(sign * r.U, "V") if r.U is not None else None,
            "I": fmt(sign * r.I, "A") if r.I is not None else None,
            "P": fmt(r.P, "W") if r.P is not None and not r.P.has(sp_I) else None,
            "reversed": sign < 0,  # the current really flows from the second pin to the first
        }
        results[label] = entry
        rows.append(f"| ${latex_name(label)}$ | {value or '—'} | "
                    f"{entry['U'] or '—'} | {entry['I'] or '—'} | {entry['P'] or '—'} |")
    outputs.append({"type": "markdown", "data": "\n".join(rows)})
    outputs += [{"type": "warning", "data": str(w.message)} for w in caught]
    return json.dumps({"results": results, "outputs": outputs}, ensure_ascii=False)


def to_output(obj) -> dict:
    for method, kind in (("_repr_svg_", "svg"), ("_repr_markdown_", "markdown"), ("_repr_latex_", "markdown")):
        data = getattr(obj, method, lambda: None)()  # sympy defines some of these and returns None
        if data is not None:
            return {"type": kind, "data": data}
    return {"type": "text", "data": repr(obj)}


def _error(err: BaseException) -> str:
    """The exception, plus the line of the cell it came from (not the library internals)."""
    lines = [frame.lineno for frame in traceback.extract_tb(err.__traceback__) if frame.filename == CELL]
    where = f"linia {lines[-1]}: " if lines else ""
    if isinstance(err, CircuitError):  # our own messages already say what is wrong
        return f"{where}{err}"
    return f"{where}{type(err).__name__}: {err}"


def run(code: str, schematics_json: str = "{}") -> str:
    """Run one cell; returns a JSON list of outputs ``{"type": ..., "data": ...}``."""
    outputs: list[dict] = []
    drawings = {name: Schematic.from_json(text) for name, text in json.loads(schematics_json).items()}

    def schemat(name: str) -> Schematic:
        if name not in drawings:
            raise KeyError(f"Nie ma schematu {name!r}. Są: {', '.join(drawings) or 'żadne'}.")
        return drawings[name]

    namespace["schemat"] = schemat
    namespace["display"] = lambda *objects: outputs.extend(to_output(o) for o in objects)
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout), warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            tree = ast.parse(code, CELL)
            last = tree.body.pop() if tree.body and isinstance(tree.body[-1], ast.Expr) else None
            exec(compile(tree, CELL, "exec"), namespace)
            if last is not None:
                value = eval(compile(ast.Expression(last.value), CELL, "eval"), namespace)
                if value is not None:
                    outputs.append(to_output(value))
        except Exception as err:  # noqa: BLE001 — every error is shown to the user
            outputs.append({"type": "error", "data": _error(err)})
    printed = stdout.getvalue()
    if printed:
        outputs.insert(0, {"type": "stream", "data": printed})
    outputs += [{"type": "warning", "data": str(w.message)} for w in caught]
    return json.dumps(outputs, ensure_ascii=False)


reset()
