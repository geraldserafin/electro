"""What goes wrong, as data: electro's errors by ``issues``, the notebook's own by their
type and fields, both said in the reader's language by the page (``shared/model/issues.ts``); anything else
(Python's NameError, …) as Python says it."""

from __future__ import annotations

import traceback

CELL = "<cell>"
"""The file name a cell's code runs as: its lines in a traceback are the cell's."""


class NotebookError(Exception):
    """One of the notebook's: its type's name and ``fields``."""

    def __init__(self, **fields: object) -> None:
        super().__init__(*fields.values())
        self.fields = fields


class NoSweepRange(NotebookError):
    """A sweep of an element with no number for its value needs its range typed (``element``)."""


class NoCircuitInCode(NotebookError):
    """The code view defines no circuit: it should assign one to ``variable``."""


class NoSuchSchematic(NotebookError):
    """No schematic cell is called ``name``; ``available``: those that are."""


class NoOutput(NotebookError):
    """A plot needs something to show: no point is named, and nothing has a capacitor's or an inductor's
    voltage."""


class NoInput(NotebookError):
    """A frequency response needs a source to be the input: the circuit has none."""


def issue(err: BaseException, units: dict[str, str] | None = None) -> dict | None:
    if isinstance(err, NotebookError):
        return {"type": type(err).__name__, **err.fields}
    from .issues import issue as core_issue

    return core_issue(err, units=units)


def error(err: BaseException) -> dict:
    """An error output: ``issue`` as data when it is ours, ``data`` as Python says it, ``line``: the cell's
    line it came from (not the library's)."""
    lines = [frame.lineno for frame in traceback.extract_tb(err.__traceback__) if frame.filename == CELL]
    said = issue(err)
    out: dict = {"type": "error", "data": f"{type(err).__name__}: {err}"}
    if said is not None:
        out["issue"] = said
    if lines:
        out["line"] = lines[-1]
    return out


def warning(message: Warning | str) -> dict:
    return {"type": "warning", "data": str(message)}
