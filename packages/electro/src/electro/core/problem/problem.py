"""A problem as one is set: a closed circuit, what is given, what is sought."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import cast

import sympy as sp

from electro.values import UNKNOWN, parse

from ..circuit.elements.parts import Part
from ..circuit.tree import Circuit, Element, is_closed, netlist
from .quantities import Quantity, Scaled

Key = Element | str | Quantity
"""What a datum is about: an element (its main parameter), a parameter by its name, or a quantity."""


class NotClosed(ValueError):
    """Only a circuit with nothing left to connect is a problem (a piece: ``blackbox``)."""


class NoSuchParameter(ValueError):
    """A value given for a name no element has."""


@dataclass(frozen=True)
class Problem:
    """Values are read once, as it is built (``"1k"`` is 1000). An element of several parameters is given
    them by name (``{diode: {"I_S": "1e-14"}}``); a quantity may be given another (``U(r1): 2 * U(r2)``).
    """

    circuit: Circuit
    given: Mapping[Key, object] = field(default_factory=dict)
    find: Sequence[Quantity] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "given", MappingProxyType({k: _read(v) for k, v in self.given.items()}))
        object.__setattr__(self, "find", tuple(self.find))
        if not is_closed(self.circuit):
            raise NotClosed()
        _check_names(self)

    @property
    def values(self) -> Mapping[Key, sp.Expr]:
        """What is given as single values (unknowns left out)."""
        return {
            k: cast(sp.Expr, v) for k, v in self.given.items() if v is not UNKNOWN and not isinstance(v, Mapping | Part)
        }


def _read(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType({w: parse(x) for w, x in value.items()})
    if isinstance(value, Quantity | Scaled | Part):
        return value
    return parse(value)


def _check_names(problem: Problem) -> None:
    names = {e.name for e, _ in netlist(problem.circuit).parts}
    for k in problem.given:
        if isinstance(k, str) and k not in names:
            raise NoSuchParameter(k)
