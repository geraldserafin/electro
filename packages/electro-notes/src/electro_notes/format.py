"""The notebook file: ``*.electro.json``.

One format for the web notebook, Python, and (later) a server that keeps each user's notes::

    {
      "format": "electro-notebook",
      "version": 2,
      "id": "5f0c…",                         # stable identity, kept across saves
      "title": "Sprawozdanie",
      "created": "2026-09-27T12:00:00Z",
      "modified": "2026-09-27T12:30:00Z",
      "settings": {"codeInPdf": true},
      "cells": [
        {"id": "a1", "type": "markdown", "source": "# Cel"},
        {"id": "b2", "type": "code", "source": "układ1.solve()", "outputs": [...], "execution": 3},
        {"id": "c3", "type": "schematic", "name": "Układ 1", "schematic": {"elements": [...], "wires": [...]},
         "view": "schematic", "results": {...}, "problems": [...], "stale": false}
      ]
    }

What a cell *is* (source, drawing, name) is the document; ``outputs`` / ``execution`` /
``results`` / ``problems`` / ``stale`` / ``view`` are what the last run or the editor left there,
kept so a file opens as it was saved (and droppable with ``strip_outputs``).

Keys this version does not know are kept as they are (``extra``), so a file written by a newer
notebook survives being opened and saved by an older one. Older files are migrated on reading.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from electro_schematic import Schematic

from .issues import (
    BrokenDrawing,
    NewerVersion,
    NoCellId,
    NoSuchSchematic,
    NotADrawing,
    NotAnObject,
    NotANotebook,
    NotJson,
    NotText,
    NoVersion,
    OtherFormat,
    RepeatedCellId,
    RepeatedSchematicName,
    SchematicExists,
    UnknownCellType,
    UnnamedSchematic,
)

FORMAT = "electro-notebook"
VERSION = 2


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def new_id() -> str:
    return uuid.uuid4().hex[:8]


# --------------------------------------------------------------------------- cells


@dataclass
class MarkdownCell:
    source: str = ""
    id: str = field(default_factory=new_id)
    extra: dict[str, Any] = field(default_factory=dict)

    type = "markdown"


@dataclass
class CodeCell:
    source: str = ""
    id: str = field(default_factory=new_id)
    outputs: list[dict[str, Any]] = field(default_factory=list)  # [{"type": "text" | "svg" | …, "data": …}]
    execution: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    type = "code"


@dataclass
class SchematicCell:
    name: str
    schematic: Schematic = field(default_factory=Schematic)
    id: str = field(default_factory=new_id)
    view: str = "schematic"  # "schematic" | "code": which side the notebook shows
    results: dict[str, Any] | None = None  # the last run, element by element
    problems: list[dict[str, Any]] | None = None
    stale: bool = False  # the drawing changed after that run
    extra: dict[str, Any] = field(default_factory=dict)

    type = "schematic"

    @property
    def variable(self) -> str:
        """The name code cells use for it: ``"Układ 1"`` → ``układ1``."""
        return variable(self.name)


Cell = MarkdownCell | CodeCell | SchematicCell


def variable(name: str) -> str:
    """A schematic's name as a Python variable (the notebook's rule): ``"Układ 1"`` → ``układ1``."""
    import re

    v = re.sub(r"\W", "", name.lower())
    if not v:
        return "uklad"
    return f"_{v}" if v[0].isdigit() else v


# --------------------------------------------------------------------------- the notebook


@dataclass
class Notebook:
    title: str = ""
    cells: list[Cell] = field(default_factory=list)
    code_in_pdf: bool = True
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    created: str = field(default_factory=now)
    modified: str = field(default_factory=now)
    extra: dict[str, Any] = field(default_factory=dict)  # unknown top-level keys, kept
    extra_settings: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------ building

    def add_markdown(self, source: str) -> MarkdownCell:
        return self._add(MarkdownCell(source.strip()))

    def add_code(self, source: str) -> CodeCell:
        return self._add(CodeCell(source.strip()))

    def add_schematic(self, name: str, drawing) -> SchematicCell:
        """``drawing``: a ``Schematic``, or a circuit — laid out automatically."""
        if not isinstance(drawing, Schematic):
            from electro_schematic import layout

            drawing = layout(drawing)
        if name in self.schematics:
            raise SchematicExists(name)
        return self._add(SchematicCell(name, drawing))

    def _add(self, cell):
        self.cells.append(cell)
        return cell

    # ------------------------------------------------------------------ reading

    @property
    def schematics(self) -> dict[str, Schematic]:
        """The drawings by name."""
        return {c.name: c.schematic for c in self.cells if isinstance(c, SchematicCell)}

    def schematic(self, name: str) -> Schematic:
        """A drawing by its name (``"Układ 1"``) or its variable (``układ1``)."""
        for c in self.cells:
            if isinstance(c, SchematicCell) and name in (c.name, c.variable):
                return c.schematic
        raise NoSuchSchematic(name, list(self.schematics))

    def strip_outputs(self) -> Notebook:
        """Forget what runs left behind (outputs, results): the document alone."""
        for c in self.cells:
            if isinstance(c, CodeCell):
                c.outputs, c.execution = [], None
            elif isinstance(c, SchematicCell):
                c.results, c.problems, c.stale = None, None, False
                c.extra.pop("frequency", None)  # the Bode plot (∿)
        return self

    # ------------------------------------------------------------------ writing

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.extra,
            "format": FORMAT,
            "version": VERSION,
            "id": self.id,
            "title": self.title,
            "created": self.created,
            "modified": self.modified,
            "settings": {**self.extra_settings, "codeInPdf": self.code_in_pdf},
            "cells": [_cell_to_dict(c) for c in self.cells],
        }

    def dumps(self, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    def save(self, path) -> None:
        self.modified = now()
        Path(path).write_text(self.dumps() + "\n", encoding="utf-8")

    def __repr__(self) -> str:
        kinds = [c.type for c in self.cells]
        counts = ", ".join(f"{kinds.count(k)} {k}" for k in ("markdown", "code", "schematic") if k in kinds)
        return f"Notebook({self.title!r}: {counts or 'pusty'})"


def _cell_to_dict(c: Cell) -> dict[str, Any]:
    out: dict[str, Any] = {**c.extra, "id": c.id, "type": c.type}
    if isinstance(c, MarkdownCell):
        out["source"] = c.source
    elif isinstance(c, CodeCell):
        out |= {"source": c.source, "outputs": c.outputs}
        if c.execution is not None:
            out["execution"] = c.execution
    else:
        out |= {"name": c.name, "schematic": json.loads(c.schematic.to_json()), "view": c.view}
        if c.results is not None:
            out["results"] = c.results
        if c.problems is not None:
            out["problems"] = c.problems
        if c.stale:
            out["stale"] = True
    return out


# --------------------------------------------------------------------------- reading files


def load(path) -> Notebook:
    """Read a ``.electro.json`` file (any version this library knows)."""
    return loads(Path(path).read_text(encoding="utf-8"))


def loads(text: str) -> Notebook:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as err:
        raise NotJson(err.lineno, err.msg) from None
    return from_dict(data)


def from_dict(data: Any) -> Notebook:
    data = migrate(data)
    _check(data)
    known = {"format", "version", "id", "title", "created", "modified", "settings", "cells"}
    settings = dict(data.get("settings") or {})
    return Notebook(
        title=data.get("title", ""),
        cells=[_cell_from_dict(c, f"cells[{i}]") for i, c in enumerate(data["cells"])],
        code_in_pdf=bool(settings.pop("codeInPdf", True)),
        id=data["id"],
        created=data["created"],
        modified=data["modified"],
        extra={k: v for k, v in data.items() if k not in known},
        extra_settings=settings,
    )


def migrate(data: Any) -> dict[str, Any]:
    """Any known version → the current one (a new dict; the input is left alone)."""
    if not isinstance(data, dict) or not isinstance(data.get("cells"), list):
        raise NotANotebook()
    data = json.loads(json.dumps(data))  # a deep copy
    version = data.get("version")
    if data.get("format", FORMAT) != FORMAT:
        raise OtherFormat(str(data["format"]))
    if version == 1:  # before the file format had a name, an id and settings
        stamp = now()
        data = {
            "format": FORMAT,
            "version": 2,
            "id": uuid.uuid4().hex,
            "title": data.get("title", ""),
            "created": stamp,
            "modified": stamp,
            "settings": {"codeInPdf": data.get("codeInPdf", True)},
            "cells": [_cell_v1(c) for c in data["cells"]],
        }
        version = 2
    if not isinstance(version, int):
        raise NoVersion()
    if version > VERSION:
        raise NewerVersion(version, VERSION)
    return data


def _cell_v1(cell: Any) -> Any:
    if isinstance(cell, dict) and cell.get("type") == "schematic":
        # v1: measurements typed next to the drawing and a Markdown table of results;
        # both went away (readings live on the meters, results are recomputed)
        cell = {k: v for k, v in cell.items() if k not in ("data", "outputs")}
    return cell


def _check(data: dict[str, Any]) -> None:
    for key, kind in (("id", str), ("title", str), ("created", str), ("modified", str)):
        if not isinstance(data.get(key), kind):
            raise NotText(key)
    if not isinstance(data.get("settings", {}), dict):
        raise NotAnObject("settings")
    ids: set[str] = set()
    names: set[str] = set()
    for i, c in enumerate(data["cells"]):
        where = f"cells[{i}]"
        if not isinstance(c, dict):
            raise NotAnObject(where)
        if not isinstance(c.get("id"), str) or not c["id"]:
            raise NoCellId(f"{where}.id")
        if c["id"] in ids:
            raise RepeatedCellId(f"{where}.id", c["id"])
        ids.add(c["id"])
        if c.get("type") not in ("markdown", "code", "schematic"):
            raise UnknownCellType(f"{where}.type", repr(c.get("type")))
        if c["type"] != "schematic" and not isinstance(c.get("source"), str):
            raise NotText(f"{where}.source")
        if c["type"] == "schematic":
            if not isinstance(c.get("name"), str) or not c["name"].strip():
                raise UnnamedSchematic(f"{where}.name")
            if c["name"] in names:
                raise RepeatedSchematicName(f"{where}.name", c["name"])
            names.add(c["name"])
            drawing = c.get("schematic")
            if (
                not isinstance(drawing, dict)
                or not isinstance(drawing.get("elements"), list)
                or not isinstance(drawing.get("wires"), list)
            ):
                raise NotADrawing(f"{where}.schematic")


def _cell_from_dict(c: dict[str, Any], where: str) -> Cell:
    if c["type"] == "markdown":
        return MarkdownCell(c["source"], c["id"], _rest(c, "source"))
    if c["type"] == "code":
        return CodeCell(
            c["source"],
            c["id"],
            list(c.get("outputs") or []),
            c.get("execution"),
            _rest(c, "source", "outputs", "execution"),
        )
    try:
        drawing = Schematic.from_json(json.dumps(c["schematic"]))
    except (TypeError, KeyError) as err:
        raise BrokenDrawing(f"{where}.schematic", repr(err)) from None
    return SchematicCell(
        c["name"],
        drawing,
        c["id"],
        c.get("view", "schematic"),
        c.get("results"),
        c.get("problems"),
        bool(c.get("stale", False)),
        _rest(c, "name", "schematic", "view", "results", "problems", "stale"),
    )


def _rest(c: dict[str, Any], *known: str) -> dict[str, Any]:
    return {k: v for k, v in c.items() if k not in ("id", "type", *known)}
