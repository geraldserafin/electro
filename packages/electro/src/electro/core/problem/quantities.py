"""What may be given or sought of a circuit, written as a book writes it: ``I(r1)``, ``U(r1)``, ``V(a)``."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import sympy as sp

from ..circuit.tree import GND, Element, Net, Node


class _Scalable:
    """A quantity times a number, ``2 * U(r2)``: for a condition between quantities (U₁ = 2·U₂)."""

    def __rmul__(self, k: object) -> Scaled:
        return Scaled(cast(sp.Expr, sp.sympify(k)), cast("Quantity", self))

    __mul__ = __rmul__


@dataclass(frozen=True)
class Current(_Scalable):
    """Of an element of two terminals: from ``a`` to ``b`` through it; of more, into it ``at`` one."""

    of: Element
    at: str | None = None


@dataclass(frozen=True)
class Voltage(_Scalable):
    """Of an element of two terminals: the drop from ``a`` to ``b``."""

    of: Element


@dataclass(frozen=True)
class Parameter(_Scalable):
    """An element's parameter: ``which`` of several (a diode's ``"I_S"``), ``""`` its main one."""

    of: Element
    which: str = ""


@dataclass(frozen=True)
class Potential(_Scalable):
    at: Node | Net


@dataclass(frozen=True)
class Across(_Scalable):
    """V_a − V_b."""

    a: Node | Net
    b: Node | Net


@dataclass(frozen=True)
class Power(_Scalable):
    """What an element of two terminals takes, U·I (a source: minus what it gives)."""

    of: Element


Quantity = Current | Voltage | Parameter | Potential | Across | Power


@dataclass(frozen=True)
class Scaled:
    factor: sp.Expr
    of: Quantity


def I(e: Element, at: str | None = None) -> Current:
    return Current(e, at)


def U(a: Element | Node | Net, b: Node | Net | None = None) -> Voltage | Across:
    """Of an element, or between two points (one: against ground)."""
    return Voltage(a) if isinstance(a, Element) else Across(a, b if b is not None else GND)


def P(e: Element) -> Power:
    return Power(e)


def V(p: Node | Net) -> Potential:
    return Potential(p)


def element_of(q: Quantity | Scaled) -> Element | None:
    match q:
        case Current(e) | Voltage(e) | Parameter(e) | Power(e):
            return e
        case Scaled(_, x):
            return element_of(x)
    return None


def points_of(q: Quantity | Scaled) -> tuple[Node | Net, ...]:
    match q:
        case Potential(p):
            return (p,)
        case Across(a, b):
            return (a, b)
        case Scaled(_, x):
            return points_of(x)
    return ()
