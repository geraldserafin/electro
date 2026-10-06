"""electro: circuits as components — composed with ``>>``, ``@``, ``|``, ``~``, ``-``, each a relation of its
ends — and a solver that puts values into one and works out a frame of it, or frame after frame in time."""

from .circuit.elements import *
from .circuit.elements import __all__ as _elements
from .circuit.elements.parts import Part, part
from .circuit.kind import Case, Cases, Kind, Terminals, two_terminal
from .circuit.netlist import ElementTwice, JoinsNodes
from .circuit.time import TIME, D, Pre, rising, square, when
from .circuit.tree import GND, BadName, Circuit, Element, Net, Node, is_closed, netlist
from .circuit.wiring import cap, cup, swap, wire
from .problem.problem import NoSuchParameter, NotClosed, Problem
from .problem.quantities import Across, Current, I, P, Parameter, Potential, Power, U, V, Voltage
from .simulation.errors import NoConvergence, NoSuchInput
from .simulation.simulate import simulate
from .simulation.trace import Trace
from .solver.ac import AC, settled, solve
from .solver.analysis import DC, Step
from .solver.errors import Ambiguous, Contradiction, MissingData, NotLinear, NotSimulated, Undetermined, ValueNeeded
from .solver.solution import Solution, SolutionStep
from .solver.step import Frame, StepFunction, step_function

__all__ = [
    "AC",
    "DC",
    "GND",
    "TIME",
    "Across",
    "Ambiguous",
    "BadName",
    "Case",
    "Cases",
    "Circuit",
    "Contradiction",
    "Current",
    "D",
    "Element",
    "ElementTwice",
    "Frame",
    "I",
    "JoinsNodes",
    "Kind",
    "MissingData",
    "Net",
    "NoConvergence",
    "NoSuchInput",
    "NoSuchParameter",
    "Node",
    "NotClosed",
    "NotLinear",
    "NotSimulated",
    "P",
    "Parameter",
    "Part",
    "Potential",
    "Power",
    "Pre",
    "Problem",
    "Solution",
    "SolutionStep",
    "Step",
    "StepFunction",
    "Terminals",
    "Trace",
    "U",
    "Undetermined",
    "V",
    "ValueNeeded",
    "Voltage",
    "cap",
    "cup",
    "is_closed",
    "netlist",
    "part",
    "rising",
    "settled",
    "simulate",
    "solve",
    "square",
    "step_function",
    "swap",
    "two_terminal",
    "when",
    "wire",
    *_elements,
]
