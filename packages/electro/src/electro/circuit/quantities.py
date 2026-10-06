"""What may be given or sought of a circuit, written as a book writes it: ``I(r1)``, ``U(r1)``, ``V(a)``."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import sympy as sp

from .element import Element
from .points import GND, Node


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
    at: Node


@dataclass(frozen=True)
class Across(_Scalable):
    """V_a − V_b."""

    a: Node
    b: Node


@dataclass(frozen=True)
class Power(_Scalable):
    """What an element of two terminals takes, U·I (a source: minus what it gives)."""

    of: Element


@dataclass(frozen=True)
class Sum(_Scalable):
    """Quantities added, each times its number: a loop's current, the current along a wire (``Scaled``)."""

    terms: tuple[Scaled, ...]


Quantity = Current | Voltage | Parameter | Potential | Across | Power | Sum


@dataclass(frozen=True)
class Scaled:
    factor: sp.Expr
    of: Quantity


def I(e: Element, at: str | None = None) -> Current:
    return Current(e, at)


def U(a: Element | Node, b: Node | None = None) -> Voltage | Across:
    """Of an element, or between two points (one: against ground)."""
    return Across(a, b if b is not None else GND) if isinstance(a, Node) else Voltage(a)


def P(e: Element) -> Power:
    return Power(e)


def V(p: Node) -> Potential:
    return Potential(p)
