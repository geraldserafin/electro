"""What solving can say instead of an answer."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import sympy as sp

from ..problem.quantities import Quantity


class Undetermined(ValueError):
    """What is sought does not follow from what is given."""


class Contradiction(Undetermined):
    """No circuit fits the data. ``data``: the given ones that clash, without any one of which it fits."""

    def __init__(self, message: str, data: Sequence[object] = ()) -> None:
        super().__init__(message)
        self.data = tuple(data)


class Ambiguous(Undetermined):
    """More than one circuit fits (a resistance from its power): ``options``, the values each takes."""

    def __init__(self, options: Sequence[Mapping[sp.Symbol, sp.Expr]]) -> None:
        super().__init__(f"{len(options)} solutions: one more datum picks one")
        self.options = tuple(dict(o) for o in options)


class MissingData(Undetermined):
    """``needed`` data more. ``options``: quantities each of which, given, would do (when one is needed);
    ``found``: what is sought and could be found."""

    def __init__(self, needed: int, options: Sequence[Quantity], found: Mapping[Quantity, sp.Expr]) -> None:
        super().__init__(f"{needed} more datum needed")
        self.needed, self.options, self.found = needed, tuple(options), dict(found)


class NotLinear(ValueError):
    """What is asked holds only for a linear circuit (a phasor, superposition)."""


class NotOnePort(ValueError):
    """A black box here is of a piece with one free end each side (1 → 1)."""


class NoConvergence(ArithmeticError):
    """A step in time Newton could not take (at ``t``)."""
