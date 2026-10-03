"""electro-schematic — circuits drawn on a grid.

A ``Schematic`` is elements (with position and rotation) and wires on a grid, stored as JSON.
It converts both ways: ``layout(circuit)`` places a circuit built in code, and
``schematic.to_circuit()`` turns a drawing into a netlist the solver understands.
"""

from .issues import Unsupported
from .layout import layout
from .model import ARROWS, GRID, KINDS, Element, Kind, Schematic, Wire, arrow_length, arrow_sign, kind_of

__all__ = [
    "ARROWS",
    "GRID",
    "KINDS",
    "Element",
    "Kind",
    "Schematic",
    "Unsupported",
    "Wire",
    "arrow_length",
    "arrow_sign",
    "kind_of",
    "layout",
]
