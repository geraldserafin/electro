"""The prototype of the redesign (packages/electro/DESIGN.md), beside the library, not yet in it.

``circuit`` says what a circuit is, ``problem`` what is asked of it; ``solver`` and ``methods`` compute.
"""

from .circuit.elements import (
    CCCS,
    CCVS,
    NOT,
    V_HIGH,
    V_T,
    VCCS,
    VCVS,
    Ammeter,
    Capacitor,
    Coupled,
    CurrentSource,
    DFlipFlop,
    Diode,
    DiodeDrop,
    Hole,
    Inductor,
    Norator,
    Nullator,
    OpAmp,
    Open,
    Resistor,
    Transformer,
    VoltageSource,
    Wire,
)
from .circuit.kind import Case, Cases, Kind, Terminals, two_terminal
from .circuit.netlist import ElementTwice, JoinsNodes, Netlist
from .circuit.time import TIME, D, Pre, rising, square, when
from .circuit.tree import GND, Circuit, Element, Net, Node, free, is_closed, netlist
from .circuit.wiring import at, beside, cap, close, cup, loop, parallel, rebuild, series, wire
from .methods.fill import Filled, fill
from .methods.response import Response, respond
from .methods.simplify import Reduction, simplify
from .methods.superposition import Superposition, superposition
from .methods.sweep import Sweep, sweep
from .methods.tolerance import Spread, tolerance
from .methods.two_points import Thevenin, between, resistance, thevenin
from .problem.data import problem_from_data, problem_to_data
from .problem.problem import NoSuchParameter, NotClosed, Problem
from .problem.quantities import Across, Current, I, P, Parameter, Potential, Power, U, V, Voltage
from .solver.analysis import AC, DC, Step
from .solver.errors import (
    Ambiguous,
    Contradiction,
    MissingData,
    NoConvergence,
    NotLinear,
    NotOnePort,
    Undetermined,
)
from .solver.laws import is_linear, is_source
from .solver.port import blackbox, matches
from .solver.relation import Equation, Origin, Relation, hide, join
from .solver.simulate import Trace, simulate
from .solver.solution import Solution, SolutionStep
from .solver.solve import solve
from .solver.system import relation

__all__ = [
    "AC",
    "CCCS",
    "CCVS",
    "DC",
    "GND",
    "TIME",
    "V_HIGH",
    "V_T",
    "VCCS",
    "VCVS",
    "Across",
    "Ambiguous",
    "Ammeter",
    "Capacitor",
    "Case",
    "Cases",
    "Circuit",
    "Contradiction",
    "Coupled",
    "Current",
    "CurrentSource",
    "D",
    "DFlipFlop",
    "Diode",
    "DiodeDrop",
    "Element",
    "ElementTwice",
    "Equation",
    "Filled",
    "Hole",
    "I",
    "Inductor",
    "JoinsNodes",
    "Kind",
    "MissingData",
    "Net",
    "Netlist",
    "Node",
    "NoConvergence",
    "NoSuchParameter",
    "Norator",
    "NOT",
    "NotClosed",
    "NotLinear",
    "NotOnePort",
    "Nullator",
    "OpAmp",
    "Open",
    "Origin",
    "P",
    "Parameter",
    "Potential",
    "Power",
    "Pre",
    "Problem",
    "Reduction",
    "Relation",
    "Resistor",
    "Response",
    "Solution",
    "SolutionStep",
    "Spread",
    "Step",
    "Superposition",
    "Sweep",
    "Terminals",
    "Thevenin",
    "Trace",
    "Transformer",
    "U",
    "Undetermined",
    "V",
    "Voltage",
    "VoltageSource",
    "Wire",
    "at",
    "beside",
    "between",
    "blackbox",
    "cap",
    "close",
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
    "rising",
    "series",
    "simplify",
    "simulate",
    "solve",
    "square",
    "superposition",
    "sweep",
    "thevenin",
    "tolerance",
    "two_terminal",
    "when",
    "wire",
]
