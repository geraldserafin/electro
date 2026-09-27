"""electro-render — how circuits look: SVG schematics and worked solutions.

Positions come from ``electro-schematic`` (drawn on a grid, or laid out from code);
this package only draws them, with one symbol library shared with the web editor.

    >>> from electro import *
    >>> from electro_render import schematic, steps
    >>> c = supply(12) + Resistor(10) + Resistor() + ground
    >>> sol = c.solve(I_R_1=0.5)
    >>> schematic(c, sol).save("uklad.svg")
    >>> print(steps(sol))
"""

from .schematic import Svg, schematic
from .symbols import symbol_library, symbol_library_json
from .trace import Markdown, steps

__all__ = ["Markdown", "Svg", "schematic", "steps", "symbol_library", "symbol_library_json"]
