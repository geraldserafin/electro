"""The library of elements: each a kind, its laws and nothing else."""

from .basic import Capacitor, CurrentSource, Inductor, Resistor, VoltageSource
from .controlled import CCCS, CCVS, VCCS, VCVS
from .diodes import V_T, Diode, DiodeDrop
from .ideal import Ammeter, Hole, Norator, Nullator, OpAmp, Open, Wire
from .logic import V_HIGH, DFlipFlop, Not
from .magnetic import Coupled, Transformer

ALL = (
    Resistor,
    Capacitor,
    Inductor,
    VoltageSource,
    CurrentSource,
    Wire,
    Open,
    Nullator,
    Norator,
    Hole,
    Ammeter,
    OpAmp,
    VCVS,
    VCCS,
    CCVS,
    CCCS,
    Transformer,
    Coupled,
    Diode,
    DiodeDrop,
    Not,
    DFlipFlop,
)

__all__ = [
    "ALL",
    "CCCS",
    "CCVS",
    "V_HIGH",
    "V_T",
    "VCCS",
    "VCVS",
    "Ammeter",
    "Capacitor",
    "Coupled",
    "CurrentSource",
    "DFlipFlop",
    "Diode",
    "DiodeDrop",
    "Hole",
    "Inductor",
    "Norator",
    "Not",
    "Nullator",
    "OpAmp",
    "Open",
    "Resistor",
    "Transformer",
    "VoltageSource",
    "Wire",
]
