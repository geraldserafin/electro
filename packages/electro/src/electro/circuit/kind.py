"""What an element is apart from any one of them: its terminals and its laws, said once (DESIGN.md §13).

A law is an expression that is zero. It speaks of each terminal's potential, the current into the element
there, and the element's own inner quantities (a flux, a state), in the words of ``time``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field

import sympy as sp

from .tree import Element


@dataclass(frozen=True)
class Terminals:
    """What a law speaks of: each terminal's potential ``V`` and the current ``I`` into the element
    there, and its inner quantities by name."""

    V: Mapping[str, sp.Expr]
    I: Mapping[str, sp.Expr]
    inner: Callable[[str], sp.Symbol]

    def across(self, a: str, b: str) -> sp.Expr:
        """V_a − V_b."""
        return self.V[a] - self.V[b]


Params = Mapping[str, sp.Symbol]
"""An element's parameters by name; ``""`` is its main one (R, C, E)."""


@dataclass(frozen=True)
class Case:
    """One way an element may be (a diode on, or off): its laws then, and what must hold for it to be
    that way, each ``holds`` ≥ 0."""

    name: str
    laws: tuple[sp.Expr, ...]
    holds: tuple[sp.Expr, ...] = ()


@dataclass(frozen=True)
class Cases:
    """An element of several ways (piecewise: a textbook diode, a switch). The circuit decides which: the
    one whose ``holds`` hold."""

    cases: tuple[Case, ...]


Laws = Callable[[Terminals, Params], Sequence[sp.Expr] | Cases]


@dataclass(frozen=True)
class Kind:
    """A kind of element. The currents into an element always add up to zero (charge is kept): the
    last terminal's is minus the others', so no law can break it.

    ``parameters`` are named, ``""`` being the main one, given as the element's value. ``defaults`` is
    what a parameter is when nothing is given; ``positive`` lists those never negative (a resistance);
    ``inputs``, those the world sets while it runs (a hand on a switch, the light on a sensor, a
    microcontroller on its pin): on paper each is a datum like any other. ``shows``: what a page reads of it
    besides its currents and inner quantities — a voltage between two of its terminals, or the current into
    one, by name. ``modes``: a board's pin's ways (``"high"``, ``"pullup"``), each its conductance to the pin's
    source and that source's voltage, set as the pin's ``_G`` and ``_E``. ``ground``: its last terminal, not
    drawn, is on ground (an op-amp's supply return): it has one end fewer."""

    name: str
    prefix: str
    terminals: tuple[str, ...]
    laws: Laws = field(repr=False)
    parameters: tuple[str, ...] = ("",)
    defaults: tuple[tuple[str, object], ...] = ()
    positive: tuple[str, ...] = ()
    inputs: tuple[str, ...] = ()
    shows: tuple[tuple[str, tuple[str, str] | str], ...] = ()
    modes: tuple[tuple[str, tuple[float, float]], ...] = ()
    ground: bool = False

    def __call__(self, name: str | None = None) -> Element:
        return Element(self, name)

    def __repr__(self) -> str:
        return self.name


def two_terminal(
    name: str, prefix: str, law: Callable[[sp.Expr, sp.Expr, sp.Symbol], sp.Expr], positive: bool = False
) -> Kind:
    """A kind of one law of ``U`` (the drop from ``a`` to ``b``), ``I`` (from ``a`` to ``b``) and its
    parameter."""
    return Kind(
        name,
        prefix,
        ("a", "b"),
        lambda t, p: [law(t.V["a"] - t.V["b"], t.I["a"], p[""])],
        positive=("",) if positive else (),
    )
