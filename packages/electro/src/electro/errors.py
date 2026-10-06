"""What solving can say instead of an answer."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import sympy as sp

from .circuit.quantities import Quantity


class Undetermined(ValueError):
    """What is sought does not follow from what is given. ``circuit``, ``values``, ``frame``: what was solved
    (set where it is)."""

    circuit: object = None
    values: Mapping = {}
    frame: object = None


class Contradiction(Undetermined):
    """No circuit fits the data."""


class Ambiguous(Undetermined):
    """More than one circuit fits (a resistance from its power): ``options``, the values each takes."""

    def __init__(self, options: Sequence[Mapping[sp.Symbol, sp.Expr]]) -> None:
        super().__init__(f"{len(options)} solutions: one more datum picks one")
        self.options = tuple(dict(o) for o in options)


class MissingData(Undetermined):
    """``targets``: what is sought and could not be found; ``needed`` data more; ``found``: what is sought and
    could be found; ``solution``, ``lacking``: where, and what of the targets is still free."""

    solution: object = None
    lacking: tuple[sp.Expr, ...] = ()

    def __init__(self, needed: int, found: Mapping[Quantity, sp.Expr], targets: Sequence[Quantity] = ()) -> None:
        super().__init__(f"{needed} more datum needed")
        self.needed, self.found, self.targets = needed, dict(found), tuple(targets)


class NotLinear(ValueError):
    """What is asked holds only for a linear circuit (a phasor, superposition)."""


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
