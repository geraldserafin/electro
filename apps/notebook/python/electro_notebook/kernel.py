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
