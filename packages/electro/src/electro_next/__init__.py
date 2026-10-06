"""electro: circuits as elements — a resistor is one, so is ``E >> R`` and every circuit — each a relation of
its ends, joined with ``>>``, ``@``, ``|``, ``~``, ``-``, what is inside eliminated as they are; and every
frame of one worked out from its frame formula: ``circuit.final(values)`` where it comes to,
``circuit.simulate(values, until)`` frame after frame."""

from .algebra import Case, Cases, SolutionStep
from .element import BadName, Element, ElementTwice, JoinsNodes, Terminals, WrongEnds
from .elements import *
from .elements import __all__ as _elements
from .elements.physics import V_T
from .errors import Ambiguous, Contradiction, MissingData, NotLinear, Undetermined
from .formula import NoSuchParameter, NotClosed
from .frame import AC, DC, Step
from .names import NoSuchQuantity
from .parts import BJT_PARTS, DIODE_PARTS, LED_COLORS, OPAMP_PARTS, Part, part
from .points import GND, Net, Node, Spider, Swap, cap, cup, swap, wire
from .quantities import Across, Current, I, P, Parameter, Potential, Power, U, V, Voltage
from .simulate import NoConvergence, NoSuchInput, NotSimulated, Trace, ValueNeeded, simulate, step_function
from .solve import Solution, final, frame_after, settled
from .time import TIME, D, Pre, rising, square, when

__all__ = [
    "BJT_PARTS",
    "DIODE_PARTS",
    "JoinsNodes",
    "LED_COLORS",
    "OPAMP_PARTS",
    "V_T",
    "AC",
    "DC",
    "GND",
    "TIME",
    "Across",
    "Ambiguous",
    "BadName",
    "Case",
    "Cases",
    "Contradiction",
    "Current",
    "D",
    "Element",
    "ElementTwice",
    "I",
    "MissingData",
    "Net",
    "NoConvergence",
    "NoSuchInput",
    "NoSuchQuantity",
    "Node",
    "NoSuchParameter",
    "NotClosed",
    "NotLinear",
    "NotSimulated",
    "P",
    "Parameter",
    "Part",
    "Potential",
    "Power",
    "Pre",
    "Solution",
    "SolutionStep",
    "Spider",
    "Step",
    "Swap",
    "Terminals",
    "Trace",
    "U",
    "Undetermined",
    "V",
    "ValueNeeded",
    "Voltage",
    "WrongEnds",
    "cap",
    "cup",
    "final",
    "frame_after",
    "part",
    "rising",
    "settled",
    "simulate",
    "square",
    "step_function",
    "swap",
    "when",
    "wire",
    *_elements,
]
