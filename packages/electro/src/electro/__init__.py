# ruff: noqa: F401, F403, F405
"""electro: circuits drawn with combinators — elements on points, joined with ``>>``, ``@``, ``|``, ``~``,
``-`` — and every frame of one worked out from its laws: ``circuit.final(values)`` where it comes to (with the
steps a book shows), ``circuit.simulate(values, until)`` frame after frame."""

from .circuit import GND, Circuit, Net, Node, Point, Spider, Swap, cap, cup, swap, wire
from .element import Case, Cases, Element, Terminals
from .elements import *
from .elements import __all__ as _elements
from .elements.physics import V_T
from .errors import (
    Ambiguous,
    BadName,
    Contradiction,
    ElementTwice,
    JoinsNodes,
    MissingData,
    NoSuchInput,
    NoSuchParameter,
    NotClosed,
    NotLinear,
    NotSimulated,
    Undetermined,
    ValueNeeded,
    WrongEnds,
)
from .frame import AC, DC, Step
from .laws import Equation, Laws, Origin, Way
from .numeric.engine import NoConvergence
from .parts import BJT_PARTS, DIODE_PARTS, LED_COLORS, OPAMP_PARTS, Part, part
from .quantities import Across, Current, I, P, Parameter, Potential, Power, Scaled, Sum, U, V, Voltage
from .simulate import Trace, simulate, step_function
from .solve import Solution, SolutionStep, final, frame_after, settled
from .time import TIME, D, Pre, rising, square, when

__all__ = [name for name, x in dict(globals()).items() if not name.startswith("_") and type(x).__name__ != "module"]
