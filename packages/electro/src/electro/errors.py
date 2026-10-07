"""What can go wrong, as data: each error says what about, in its fields."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import sympy as sp


class BadName(ValueError):
    """A name with more than letters, digits and ``_``: nothing else reaches the equations or the code."""

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.name = name


class ElementTwice(ValueError):
    """One element in two places: two elements are two objects (``Resistor("R")`` twice)."""


class JoinsNodes(ValueError):
    """``>>`` would make two different named points one: say it with the same ``Node`` instead."""


class WrongEnds(ValueError):
    """``>>`` of pieces whose ends do not meet: ``left`` ends into ``right``."""

    def __init__(self, left: int, right: int) -> None:
        super().__init__(left, right)
        self.left, self.right = left, right


class NotClosed(ValueError):
    """Only a closed circuit has values: ``left`` and ``right`` ends are still free (not on a named point)."""

    def __init__(self, left: int, right: int) -> None:
        super().__init__(left, right)
        self.left, self.right = left, right


class NoSuchParameter(ValueError):
    """A value given for a name no element has."""


class NoSuchInput(KeyError):
    """Nothing in the circuit is set from outside by that name (a switch's, a board's pin)."""

    def __init__(self, name: str, available: list[str]) -> None:
        super().__init__(name)
        self.name, self.available = name, available


class Undetermined(ValueError):
    """What is sought does not follow from what is given. ``circuit``, ``values``, ``frame``: what was solved
    (set where it is)."""

    circuit: object = None
    values: Mapping = {}
    frame: object = None


class Contradiction(Undetermined):
    """No circuit fits the data. ``data``: the given ones among the equations that clash."""

    def __init__(self, message: str, data: Sequence[object] = ()) -> None:
        super().__init__(message)
        self.data = tuple(data)


class Ambiguous(Undetermined):
    """More than one circuit fits (a resistance from its power): ``options``, the values each takes."""

    def __init__(self, options: Sequence[Mapping[sp.Symbol, sp.Expr]]) -> None:
        super().__init__(f"{len(options)} solutions: one more datum picks one")
        self.options = tuple(dict(o) for o in options)


class MissingData(Undetermined):
    """``targets``: what is sought and could not be found; ``needed`` data more; ``found``: what is sought and
    could be found."""

    def __init__(self, needed: int, found: Mapping, targets: Sequence = ()) -> None:
        super().__init__(f"{needed} more datum needed")
        self.needed, self.found, self.targets = needed, dict(found), tuple(targets)


class NotLinear(ValueError):
    """What is asked holds only for a linear circuit (a phasor of a non-linear one)."""


class NotSimulated(ValueError):
    """``label`` has no law to step in time (the textbook's diode: one of its ways, assumed on paper), or the
    circuit's laws are not one for each quantity."""

    def __init__(self, label: str) -> None:
        super().__init__(label)
        self.label = label


class ValueNeeded(ValueError):
    """A simulation needs every value: ``label``'s is not given."""

    def __init__(self, label: str) -> None:
        super().__init__(label)
        self.label = label
