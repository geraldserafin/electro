"""Why an equation holds — each law's reason as a type, for the solution's steps. Whoever shows
the steps says the reason (the notebook: in the reader's language). ``label``: the element."""

from __future__ import annotations

from dataclasses import dataclass

import sympy as sp


@dataclass(frozen=True)
class Reason:
    pass


@dataclass(frozen=True)
class Given(Reason):
    """A datum of the problem (passed to solve())."""


@dataclass(frozen=True)
class OhmsLaw(Reason):
    label: sp.Symbol


@dataclass(frozen=True)
class CapacitorOpenDC(Reason):
    """In a DC steady state a capacitor carries no current."""

    label: sp.Symbol


@dataclass(frozen=True)
class CapacitorImpedance(Reason):
    """1/(jωC)."""

    label: sp.Symbol


@dataclass(frozen=True)
class InductorShortDC(Reason):
    """In a DC steady state an inductor is a short circuit."""

    label: sp.Symbol


@dataclass(frozen=True)
class InductorImpedance(Reason):
    """jωL."""

    label: sp.Symbol


@dataclass(frozen=True)
class SourceVoltage(Reason):
    label: sp.Symbol


@dataclass(frozen=True)
class SourceCurrent(Reason):
    label: sp.Symbol


@dataclass(frozen=True)
class IdealAmmeter(Reason):
    """U = 0."""

    label: sp.Symbol


@dataclass(frozen=True)
class AmmeterReading(Reason):
    label: sp.Symbol


@dataclass(frozen=True)
class IdealVoltmeter(Reason):
    """I = 0."""

    label: sp.Symbol


@dataclass(frozen=True)
class VoltmeterReading(Reason):
    label: sp.Symbol


@dataclass(frozen=True)
class ControlVoltage(Reason):
    """A controlled source's control side senses a voltage: U_c = V_cp − V_cn, no current."""

    label: sp.Symbol


@dataclass(frozen=True)
class ControlCurrent(Reason):
    """A controlled source's control side is a branch the current goes through: U = 0."""

    label: sp.Symbol


@dataclass(frozen=True)
class ControlledSource(Reason):
    """The output of a controlled source: its gain times the control quantity."""

    label: sp.Symbol


@dataclass(frozen=True)
class IdealOpAmp(Reason):
    """V+ = V−."""

    label: sp.Symbol


@dataclass(frozen=True)
class UnknownElement(Reason):
    """A hole: U = Z·I − E."""

    label: sp.Symbol


@dataclass(frozen=True)
class VoltageAcross(Reason):
    """An element's voltage is the difference of its terminals' potentials."""

    label: sp.Symbol


@dataclass(frozen=True)
class Terminal(Reason):
    """An open circuit's terminal: ``side`` "in" / "out", ``index`` from 1."""

    side: str
    index: int


@dataclass(frozen=True)
class KirchhoffCurrent(Reason):
    """Kirchhoff's current law at ``node``."""

    node: sp.Symbol


@dataclass(frozen=True)
class CapacitorStep(Reason):
    """One step in time (backward Euler): I = C·(U − U_prev)/Δt."""

    label: sp.Symbol


@dataclass(frozen=True)
class InductorStep(Reason):
    """One step in time: U = L·(I − I_prev)/Δt."""

    label: sp.Symbol


@dataclass(frozen=True)
class SwitchClosed(Reason):
    """A closed switch (or a pressed button): U = 0."""

    label: sp.Symbol


@dataclass(frozen=True)
class SwitchOpen(Reason):
    """An open switch: I = 0."""

    label: sp.Symbol


@dataclass(frozen=True)
class PotentiometerDivider(Reason):
    """The two parts of a potentiometer, either side of the wiper, obey Ohm's law."""

    label: sp.Symbol


@dataclass(frozen=True)
class DeviceModel(Reason):
    """A semiconductor's or a chip's model (a diode's Shockley equation, a 555, an Arduino's pin)."""

    label: sp.Symbol
