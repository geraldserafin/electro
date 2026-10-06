"""The prototype of the redesign (packages/electro/DESIGN.md), beside the library, not yet in it.

``circuit`` says what a circuit is, ``problem`` what is asked of it; ``solver`` and ``methods`` compute.
"""

from .circuit.elements import *
from .circuit.elements import __all__ as _elements
from .circuit.elements.parts import Part, part
from .circuit.kind import Case, Cases, Kind, Terminals, two_terminal
from .circuit.netlist import ElementTwice, JoinsNodes, Netlist
from .circuit.time import TIME, D, Pre, rising, square, when
from .circuit.tree import GND, BadName, Circuit, Element, Net, Node, free, is_closed, netlist
from .circuit.wiring import cap, cup, wire
from .methods.ac import AC, settled, solve
from .methods.fill import Filled, fill
from .methods.response import Response, respond, responses
from .methods.simplify import Reduction, simplify
from .methods.superposition import Superposition, superposition
from .methods.sweep import Sweep, sweep, sweeps
from .methods.tolerance import Spread, spreads, tolerance
from .methods.two_points import Thevenin, between, resistance, thevenin
from .problem.netlist import from_netlist, to_netlist
from .problem.problem import NoSuchParameter, NotClosed, Problem
from .problem.quantities import Across, Current, I, P, Parameter, Potential, Power, U, V, Voltage
from .problem.spice import NoSpice, from_spice, to_spice
from .simulation.errors import NoConvergence, NoSuchInput
from .simulation.simulate import simulate
from .simulation.trace import Trace
from .solver.analysis import DC, Step
from .solver.errors import (
    Ambiguous,
    Contradiction,
    MissingData,
    NotLinear,
    NotOnePort,
    NotSimulated,
    Undetermined,
    ValueNeeded,
)
from .solver.laws import is_linear, is_source, reading, stores
from .solver.port import blackbox, matches
from .solver.relation import Equation, Origin, Relation, hide, join
from .solver.solution import Solution, SolutionStep
from .solver.step import Frame, StepFunction, step_function
from .solver.system import relation

__all__ = [
    "AC",
    "BadName",
    "Across",
    "Ambiguous",
    "Case",
    "Cases",
    "Circuit",
    "Contradiction",
    "Current",
    "D",
    "DC",
    "Element",
    "ElementTwice",
    "Equation",
    "Frame",
    "Filled",
    "GND",
    "I",
    "JoinsNodes",
    "Kind",
    "MissingData",
    "Net",
    "Netlist",
    "NoConvergence",
    "NoSuchInput",
    "NoSuchParameter",
    "Node",
    "NotClosed",
    "NotLinear",
    "NotOnePort",
    "NotSimulated",
    "Origin",
    "P",
    "Part",
    "Parameter",
    "Potential",
    "Power",
    "Pre",
    "Problem",
    "Reduction",
    "Relation",
    "Response",
    "Solution",
    "SolutionStep",
    "Spread",
    "Step",
    "StepFunction",
    "Superposition",
    "Sweep",
    "TIME",
    "Terminals",
    "Thevenin",
    "Trace",
    "U",
    "Undetermined",
    "V",
    "ValueNeeded",
    "Voltage",
    "between",
    "blackbox",
    "cap",
    "cup",
    "fill",
    "free",
    "from_netlist",
    "hide",
    "is_closed",
    "is_linear",
    "is_source",
    "join",
    "matches",
    "netlist",
    "part",
    "reading",
    "relation",
    "resistance",
    "respond",
    "responses",
    "rising",
    "simplify",
    "simulate",
    "settled",
    "solve",
    "step_function",
    "square",
    "stores",
    "superposition",
    "sweep",
    "sweeps",
    "thevenin",
    "spreads",
    "to_netlist",
    "from_spice",
    "to_spice",
    "NoSpice",
    "tolerance",
    "two_terminal",
    "when",
    "wire",
    *_elements,
]
