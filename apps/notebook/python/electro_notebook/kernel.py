"""Notebook kernel: runs cells in one shared namespace and turns results into outputs.

Every cell sees what earlier cells defined, like in Jupyter. The value of the last
expression is shown; objects with ``_repr_svg_`` / ``_repr_markdown_`` show as a
picture / formatted text, a worked solution (``steps(sol)``) as data. Schematic cells are
available as ``schemat("name")``.

Nothing here is said in words: what goes wrong is an issue type (``electro.issues``), sent
as JSON — ``{"type": "MissingData", "targets": ["R_{2}"], …}``, math in LaTeX — and the
notebook says it in the reader's language. Python's own errors (NameError, …) stay as
Python says them.
"""

from __future__ import annotations

import ast
import contextlib
import io
import json
import re
import traceback
import warnings
from dataclasses import fields, is_dataclass

import sympy as sp
from electro.components import Law
from electro.issues import Equals, Issue, IsZero, issue
from sympy import I as sp_I
from electro_render import Steps, symbol_library
from electro_schematic import Schematic
from electro_schematic.issues import Unsupported

CELL = "<cell>"
PRELUDE = """
from electro import *
from electro_render import schematic, steps
from electro_schematic import Schematic, layout
"""

namespace: dict = {}


@issue
class NoCircuitInCode(Issue, ValueError):
    """The code view defines no circuit: it should assign one, e.g. ``variable = loop(...)``."""

    variable: str


@issue
class OnlyValuesInCode(Issue, ValueError):
    """The code view made a circuit layout() cannot draw: in code, change only the values
    (add elements on the drawing)."""

    cause: Unsupported


@issue
class BadDataEntry(Issue, ValueError):
    """An entry of a schematic's data that is not ``name = value`` (e.g. ``I_R_1 = 0,5``)."""

    entry: str


@issue
class NoSuchSchematic(Issue, KeyError):
    name: str
    available: list


def reset() -> None:
    """Forget everything the cells defined."""
    namespace.clear()
    exec(PRELUDE, namespace)


def symbols() -> str:
    return json.dumps(symbol_library(), ensure_ascii=False)


def variable(name: str) -> str:
    """A schematic's name as the Python variable cells see it: ``"Układ 1"`` → ``układ1``."""
    v = re.sub(r"\W", "", name.lower())
    if not v:
        return "uklad"
    return f"_{v}" if v[0].isdigit() else v


def code(schematic_json: str, name: str) -> str:
    """A drawing as plain electro code, for the code view."""
    return Schematic.from_json(schematic_json).to_code(variable(name))


def from_code(source: str, name: str, old_json: str = "") -> str:
    """The code view edited back into a drawing: run ``source`` and lay out its circuit.

    The circuit is the variable called like the schematic (``uklad``), else the last one the
    code defines. When only values changed, the old drawing (``old_json``) keeps its layout
    with the new values; otherwise the circuit is laid out anew.
    Returns JSON ``{"schematic": ...}`` or ``{"error": {...}}`` (an error output).
    """
    from electro import Circuit
    from electro_schematic import layout
    from electro_schematic.layout import Unsupported

    var = variable(name)
    scope: dict = {}
    exec(PRELUDE, scope)
    prelude = set(scope)
    try:
        exec(compile(source, CELL, "exec"), scope)
        found = scope.get(var)
        if not isinstance(found, Circuit):
            defined = [v for k, v in scope.items() if k not in prelude and isinstance(v, Circuit)]
            if not defined:
                raise NoCircuitInCode(var)
            found = defined[-1]
        kept = _same_but_values(Schematic.from_json(old_json), found, var) if old_json else None
        if kept is not None:
            return json.dumps({"schematic": json.loads(kept.to_json())}, ensure_ascii=False)
        try:
            fresh = layout(found)
        except Unsupported as err:
            raise OnlyValuesInCode(err) from None
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
            raise BadDataEntry(entry.strip())
        given[name.strip()] = value.strip()
    return given


def simulate(schematic_json: str, data: str = "") -> str:
    """The run button of a schematic cell: solve the drawing and report every element's values.

    Returns JSON ``{"results": {id: {...}}, "problems": [{"kind": "warning" | "error", "issue": {...}}]}``:
    ``results`` go on the drawing and in the table under it; ``problems`` behind the warning
    button on the board (``text`` instead of ``issue`` for an error that is not ours).
    """
    from electro.components import notation
    from electro.values import UNKNOWN, fmt

    sch = Schematic.from_json(schematic_json)
    results: dict[str, dict] = {}
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            solution = sch.to_circuit().solve(**_parse_data(data))
        except (Issue, ValueError, KeyError) as err:
            return json.dumps({"results": {}, "problems": [_problem("error", err)]}, ensure_ascii=False)
    for label in solution.system.parts:
        r = solution[label]
        comp = r.component
        current = r.I if r.I is not None and r.I.is_real and r.I.is_number else None
        sign = -1 if current is not None and current < 0 else 1
        if r.realized is not None:
            value = notation(r.realized)
        elif comp.has_value:
            value = fmt(r.value, comp.unit) if r.value is not None else "?"
        else:
            value = ""
        results[label] = {
            "value": value,
            "solved": (comp.has_value and comp.value is UNKNOWN and r.value is not None) or r.realized is not None,
            "U": fmt(sign * r.U, "V") if r.U is not None else None,
            "I": fmt(sign * r.I, "A") if r.I is not None else None,
            "P": fmt(r.P, "W") if r.P is not None and not r.P.has(sp_I) else None,
            "reversed": sign < 0,  # the current really flows from the second pin to the first
        }
    problems = [_problem("warning", w.message) for w in caught]
    return json.dumps({"results": results, "problems": problems}, ensure_ascii=False)


def live(schematic_json: str) -> str:
    """The play button of a schematic cell: the drawing compiled for the page's engine
    (``simulation/engine.ts``), and where on the drawing each node is.

    Returns JSON ``{"program": {...}, "wires": [node per wire], "pins": {id: [node per pin]}}``
    (``null`` for a wire that touches no element), or ``{"error": {...}}`` (an error output).
    """
    from electro.sim import compile_sim

    try:
        sch = Schematic.from_json(schematic_json)
        program = compile_sim(sch.to_circuit())
    except Exception as err:  # noqa: BLE001 — shown on the board
        return json.dumps({"error": _error(err)}, ensure_ascii=False)
    names = sch.node_names()
    return json.dumps({
        "program": json.loads(program.to_json()),
        "wires": [names.get(w.points[0]) for w in sch.wires],
        "pins": {e.id: [names.get(p) for p in e.pins()] for e in sch.components()},
    }, ensure_ascii=False)


def to_json(x):
    """An issue, a reason or a solution's steps as JSON: ``{"type": "OhmsLaw", "label": "R_{1}"}``.
    Quantities and expressions become LaTeX (``R_{1}``, ``\\frac{U}{I}``), the rest stays as it is."""
    from electro_render.trace import expr, name, value

    if isinstance(x, Law):
        return {"equation": f"{expr(x.expr)} = 0", "reason": to_json(x.reason)}
    if isinstance(x, Equals):
        return f"{name(x.symbol.name)} = {value(x.value, x.unit)}"
    if isinstance(x, IsZero):
        return f"{expr(x.expr)} = 0"
    if isinstance(x, Issue) or (is_dataclass(x) and not isinstance(x, type)):
        shown = [f for f in fields(x) if f.metadata.get("shown", True)] if is_dataclass(x) else []
        return {"type": type(x).__name__, **{f.name: to_json(getattr(x, f.name)) for f in shown}}
    if isinstance(x, sp.Symbol):
        return name(x.name)
    if isinstance(x, sp.Basic):
        return expr(x)
    if isinstance(x, (list, tuple)):
        return [to_json(v) for v in x]
    return x


def _problem(kind: str, err) -> dict:
    """For the board's warning button: our issue as data, anything else as its text."""
    return {"kind": kind, "issue": to_json(err)} if isinstance(err, Issue) else {"kind": kind, "text": str(err)}


def to_output(obj) -> dict:
    if isinstance(obj, Schematic):  # a schematic cell's variable on its own: show the drawing
        from electro_render import schematic

        obj = schematic(obj)
    if isinstance(obj, Steps):
        return {"type": "solution", "data": to_json(obj)}
    if isinstance(obj, Issue):  # an error caught and shown on purpose: display(e)
        kind = "warning" if isinstance(obj, Warning) else "error"
        return {"type": "issue", "kind": kind, "data": repr(obj), "issue": to_json(obj)}
    for method, kind in (("_repr_svg_", "svg"), ("_repr_markdown_", "markdown"), ("_repr_latex_", "markdown")):
        data = getattr(obj, method, lambda: None)()  # sympy defines some of these and returns None
        if data is not None:
            return {"type": kind, "data": data}
    return {"type": "text", "data": repr(obj)}


def _error(err: BaseException) -> dict:
    """An error output: our issue as data (``issue``), anything else as Python says it; ``line``:
    the line of the cell it came from (not the library internals)."""
    lines = [frame.lineno for frame in traceback.extract_tb(err.__traceback__) if frame.filename == CELL]
    out: dict = {"type": "error", "data": repr(err) if isinstance(err, Issue) else f"{type(err).__name__}: {err}"}
    if isinstance(err, Issue):
        out["issue"] = to_json(err)
    if lines:
        out["line"] = lines[-1]
    return out


def _warning(message) -> dict:
    if isinstance(message, Issue):
        return {"type": "warning", "data": repr(message), "issue": to_json(message)}
    return {"type": "warning", "data": str(message)}


def run(code: str, schematics_json: str = "{}", standard: str = "iec") -> str:
    """Run one cell; returns a JSON list of outputs ``{"type": ..., "data": ...}``. Schematics are
    drawn with ``standard``'s symbols (the note's: "iec" or "ieee")."""
    from electro_render.symbols import use

    use(standard)
    outputs: list[dict] = []
    drawings = {name: Schematic.from_json(text) for name, text in json.loads(schematics_json).items()}

    def schemat(name: str) -> Schematic:
        if name not in drawings:
            raise NoSuchSchematic(name, list(drawings))
        return drawings[name]

    namespace["schemat"] = schemat
    for name, drawing in drawings.items():  # "Układ 1" is układ1 in code
        namespace[variable(name)] = drawing
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
            outputs.append(_error(err))
    printed = stdout.getvalue()
    if printed:
        outputs.insert(0, {"type": "stream", "data": printed})
    outputs += [_warning(w.message) for w in caught]
    return json.dumps(outputs, ensure_ascii=False)


reset()
