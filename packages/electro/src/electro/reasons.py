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
