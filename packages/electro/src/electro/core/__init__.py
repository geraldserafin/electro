"""The prototype of the redesign (packages/electro/DESIGN.md), beside the library, not yet in it.

``circuit`` says what a circuit is, ``problem`` what is asked of it; ``solver`` and ``methods`` compute.
"""

from .circuit.elements import *
from .circuit.elements import __all__ as _elements
from .circuit.kind import Case, Cases, Kind, Terminals, two_terminal
from .circuit.netlist import ElementTwice, JoinsNodes, Netlist
from .circuit.time import TIME, D, Pre, rising, square, when
from .circuit.tree import GND, Circuit, Element, Net, Node, free, is_closed, netlist
from .circuit.wiring import at, beside, cap, close, cup, loop, parallel, rebuild, series, wire
from .methods.fill import Filled, fill
from .methods.response import Response, respond, responses
from .methods.simplify import Reduction, simplify
from .methods.superposition import Superposition, superposition
from .methods.sweep import Sweep, sweep, sweeps
from .methods.tolerance import Spread, spreads, tolerance
from .methods.two_points import Thevenin, between, resistance, thevenin
from .problem.data import problem_from_data, problem_to_data
from .problem.problem import NoSuchParameter, NotClosed, Problem
from .problem.quantities import Across, Current, I, P, Parameter, Potential, Power, U, V, Voltage
from .simulation.errors import NoConvergence, NoSuchInput, NotSimulated, ValueNeeded
from .simulation.program import Program, compile_program
from .simulation.simulate import simulate
from .simulation.trace import Trace
from .solver.analysis import AC, DC, Step
from .solver.errors import (
    Ambiguous,
    Contradiction,
    MissingData,
    NotLinear,
    NotOnePort,
    Undetermined,
)
from .solver.laws import is_linear, is_source
from .solver.port import blackbox, matches
from .solver.relation import Equation, Origin, Relation, hide, join
from .solver.solution import Solution, SolutionStep
from .solver.solve import solve
from .solver.system import relation

__all__ = [
    "AC",
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
    "Parameter",
    "Potential",
    "Power",
    "Pre",
    "Problem",
    "Program",
    "Reduction",
    "Relation",
    "Response",
    "Solution",
    "SolutionStep",
    "Spread",
    "Step",
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
    "at",
    "beside",
    "between",
    "blackbox",
    "cap",
    "close",
    "compile_program",
    "cup",
    "fill",
    "free",
    "hide",
    "is_closed",
    "is_linear",
    "is_source",
    "join",
    "loop",
    "matches",
    "netlist",
    "parallel",
    "problem_from_data",
    "problem_to_data",
    "rebuild",
    "relation",
    "resistance",
    "respond",
    "responses",
    "rising",
    "series",
    "simplify",
    "simulate",
    "solve",
    "square",
    "superposition",
    "sweep",
    "sweeps",
    "thevenin",
    "spreads",
    "tolerance",
    "two_terminal",
    "when",
    "wire",
    *_elements,
]
