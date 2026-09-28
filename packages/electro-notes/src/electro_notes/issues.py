"""What can be wrong with a notebook file, as types (like ``electro.issues``: data, no sentences).
``where``: the place in the file, e.g. ``cells[2].id``."""

from __future__ import annotations

from electro.issues import Issue, issue


class FormatError(Issue, ValueError):
    """The file is not a notebook, or a broken one."""


@issue
class NotJson(FormatError):
    line: int
    reason: str  # the JSON parser's own words


@issue
class NotANotebook(FormatError):
    """No list of cells."""


@issue
class OtherFormat(FormatError):
    format: str


@issue
class NoVersion(FormatError):
    pass


@issue
class NewerVersion(FormatError):
    version: int
    known: int


@issue
class NotText(FormatError):
    where: str


@issue
class NotAnObject(FormatError):
    where: str


@issue
class NoCellId(FormatError):
    where: str


@issue
class RepeatedCellId(FormatError):
    where: str
    id: str


@issue
class UnknownCellType(FormatError):
    where: str
    found: str


@issue
class UnnamedSchematic(FormatError):
    where: str


@issue
class RepeatedSchematicName(FormatError):
    where: str
    name: str


@issue
class NotADrawing(FormatError):
    """Not ``{"elements": [...], "wires": [...]}``."""

    where: str


@issue
class BrokenDrawing(FormatError):
    where: str
    cause: str


@issue
class SchematicExists(Issue, ValueError):
    name: str


@issue
class NoSuchSchematic(Issue, KeyError):
    name: str
    available: list
