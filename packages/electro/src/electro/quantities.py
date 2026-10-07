"""What may be given or sought of a circuit, written as a book writes it: ``I(r1)``, ``U(r1)``, ``V(a)``. Each
is an expression in the elements' own variables (``expr``); a datum ``{I(R): 2}`` is the equation
``I(R).expr − 2 = 0``."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import sympy as sp

from .circuit import GND, Node
from .element import Element


class _Quantity:
    def __rmul__(self, k: object) -> Scaled:
        """``2 * U(r2)``: for a datum between quantities (U₁ = 2·U₂)."""
        return Scaled(cast(sp.Expr, sp.sympify(k)), cast("Quantity", self))

    __mul__ = __rmul__

    @property
    def expr(self) -> sp.Expr:
        raise NotImplementedError


@dataclass(frozen=True)
class Current(_Quantity):
    """Of an element of two terminals: from its first through it; of more, into it ``at`` one."""

    of: Element
    at: str | None = None

    @property
    def expr(self) -> sp.Expr:
        return self.of.I[self.at or self.of.terminals[0]]


@dataclass(frozen=True)
class Voltage(_Quantity):
    """Of an element of two terminals: the drop from its first to its second."""

    of: Element

    @property
    def expr(self) -> sp.Expr:
        a, b = self.of.terminals[:2]
        return self.of.V[a] - self.of.V[b]


@dataclass(frozen=True)
class Parameter(_Quantity):
    """An element's parameter: ``which`` of several (a diode's ``"I_S"``), ``""`` its main one."""

    of: Element
    which: str = ""

    @property
    def expr(self) -> sp.Expr:
        return self.of.P[self.which]


@dataclass(frozen=True)
class Potential(_Quantity):
    at: Node

    @property
    def expr(self) -> sp.Expr:
        return self.at.potential


@dataclass(frozen=True)
class Across(_Quantity):
    """V_a − V_b."""

    a: Node
    b: Node

    @property
    def expr(self) -> sp.Expr:
        return self.a.potential - self.b.potential


@dataclass(frozen=True)
class Power(_Quantity):
    """What an element of two terminals takes, U·I (a source: minus what it gives); in AC, the average."""

    of: Element

    @property
    def expr(self) -> sp.Expr:
        return Voltage(self.of).expr * Current(self.of).expr


@dataclass(frozen=True)
class Sum(_Quantity):
    """Quantities added, each times its number: a loop's current, the current along a wire."""

    terms: tuple[Scaled, ...]

    @property
    def expr(self) -> sp.Expr:
        return sp.Add(*(t.expr for t in self.terms))


@dataclass(frozen=True)
class Scaled:
    factor: sp.Expr
    of: Quantity

    @property
    def expr(self) -> sp.Expr:
        return self.factor * self.of.expr


Quantity = Current | Voltage | Parameter | Potential | Across | Power | Sum


def I(e: Element, at: str | None = None) -> Current:
    return Current(e, at)


def U(a: Element | Node, b: Node | None = None) -> Voltage | Across:
    """Of an element, or between two points (one: against ground)."""
    return Across(a, b if b is not None else GND) if isinstance(a, Node) else Voltage(a)


def P(e: Element) -> Power:
    return Power(e)


def V(p: Node) -> Potential:
    return Potential(p)
