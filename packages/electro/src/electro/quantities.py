"""What may be given or sought of a circuit, written as a book writes it: ``I(r1)``, ``U(r1)``, ``V(a)``. Each
is an expression in the elements' own variables (``expr``). The values a circuit is given are its parameters'
(``given``: ``{R: "1k"}``) and data on quantities (``data``: ``{I(R): 2}`` is the equation I(R) − 2 = 0)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

import sympy as sp

from .circuit import GND, Circuit, Node
from .element import Element
from .errors import NoSuchParameter
from .laws import Equation, Origin
from .parts import Part
from .values import UNKNOWN, parse


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


# The values a circuit is given


def given(circuit: Circuit, values: Mapping) -> dict[sp.Symbol, sp.Expr]:
    """Each parameter's value: its kind's default, unless given."""
    out = {e.P[w]: sp.sympify(parse(d)) for e in circuit.members for w, d in e.defaults.items()}
    for key, value in values.items():
        out |= _parameters(circuit, key, value)
    return out


def _parameters(circuit: Circuit, key: object, value: object) -> dict[sp.Symbol, sp.Expr]:
    """The parameters one entry of the values gives: an element's value (its main parameter), several by name
    (``{D: {"I_S": …}}``), a real part's (``part("1N4148")``), or a name elements share (``{"R": 10}``)."""
    match key, value:
        case Element(), Part():
            return _known({key.P[w]: x for w, x in value.parameters(key.kind).items()})
        case Element(), Mapping():
            return _known({key.P[w]: x for w, x in value.items()})
        case Element(), _:
            return _known({key.P[""]: value})
        case str(), _:
            if not any(x.name == key for e in circuit.members for x in e.P.values()):
                raise NoSuchParameter(key)
            return _known({sp.Symbol(key): value})
    return {}


def _known(values: Mapping[sp.Symbol, object]) -> dict[sp.Symbol, sp.Expr]:
    """Each value read, those left to find (``"?"``) left out."""
    read = {x: parse(v) for x, v in values.items()}
    return {x: sp.sympify(v) for x, v in read.items() if v is not UNKNOWN}


def data(values: Mapping) -> list[Equation]:
    """The data on quantities (``I(R): 2``, ``U(R_1): 2 * U(R_2)``), each an equation."""
    return [
        Equation(key.expr - _side(value), Origin("given", key))
        for key, value in values.items()
        if isinstance(key, _Quantity | Scaled) and _side(value) is not UNKNOWN
    ]


def _side(value: object):
    """A datum's value: another quantity, or a value read."""
    return value.expr if isinstance(value, _Quantity | Scaled) else parse(value)
