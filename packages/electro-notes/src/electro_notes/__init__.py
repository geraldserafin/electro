"""electro_notes — the notebook file (``*.electro.json``): read, write, migrate, check.

    >>> from electro_notes import Notebook, load
    >>> nb = load("sprawozdanie.electro.json")
    >>> nb.schematic("Układ 1").solve(find="E")      # a drawing, as a circuit
    >>> nb.add_code("układ1.solve()"); nb.save("sprawozdanie.electro.json")
"""

from .format import (
    FORMAT, VERSION, Cell, CodeCell, FormatError, MarkdownCell, Notebook, SchematicCell, from_dict, load, loads,
    migrate, variable,
)

__all__ = [
    "FORMAT", "VERSION", "Cell", "CodeCell", "FormatError", "MarkdownCell", "Notebook", "SchematicCell",
    "from_dict", "load", "loads", "migrate", "variable",
]
