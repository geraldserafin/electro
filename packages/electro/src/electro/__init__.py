"""electro — circuits as morphisms of a hypergraph category, with a step-by-step solver.

    >>> from electro import *
    >>> c = supply(12) + Resistor(10) + Resistor() + ground
    >>> sol = c.solve(I_R1=0.5)
    >>> sol["R2"].value
    14
"""

from sympy import Eq, Symbol, symbols

from .analysis import Relation, Thevenin, blackbox, equivalent, resistance
from .codegen import code
from .circuit import (
    GROUND, Circuit, ground, join, loop, net, node, open_end, parallel, series, shunt, spider,
    split, swap, wire, wires,
)
from .components import (
    Ammeter, Capacitor, Component, CurrentSource, Hole, Inductor, Law, Model, NoValue, OpAmp, Resistor,
    TwoTerminal, VoltageSource, Voltmeter, supply,
)
from .issues import Issue
from .solver import Ambiguous, CircuitError, Contradiction, Diagnosis, I, MissingData, P, Solution, U, V, solve
from .values import fmt, parse

__all__ = [
    "GROUND", "Circuit", "ground", "join", "loop", "net", "node", "open_end", "parallel", "series",
    "shunt", "spider", "split", "swap", "wire", "wires",
    "Ammeter", "Capacitor", "Component", "CurrentSource", "Hole", "Inductor", "Law", "Model", "NoValue",
    "OpAmp", "Resistor", "TwoTerminal", "VoltageSource", "Voltmeter", "supply",
    "Relation", "Thevenin", "blackbox", "code", "equivalent", "resistance",
    "Ambiguous", "CircuitError", "Contradiction", "Diagnosis", "MissingData", "I", "P", "U", "V", "Solution", "solve",
    "fmt", "parse", "Eq", "Symbol", "symbols",
]
