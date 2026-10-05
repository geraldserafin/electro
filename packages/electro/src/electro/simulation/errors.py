"""What a simulation can say instead of running."""

from __future__ import annotations

from collections.abc import Sequence


class NotSimulated(ValueError):
    """``label`` has no law to run in time (the textbook's diode: one of its ways, assumed on paper), or the
    circuit's laws are not one for each quantity."""

    def __init__(self, label: str) -> None:
        super().__init__(label)
        self.label = label


class ValueNeeded(ValueError):
    """A simulation needs every value: ``label``'s is not given."""

    def __init__(self, label: str) -> None:
        super().__init__(label)
        self.label = label


class NoSuchInput(KeyError):
    """Nothing in the circuit is set from outside by that name (a switch's, a board's pin)."""

    def __init__(self, name: str, available: Sequence[str]) -> None:
        super().__init__(name)
        self.name, self.available = name, list(available)


class NoConvergence(ArithmeticError):
    """The circuit's state at ``time`` (seconds) could not be found, even in tiny steps."""

    def __init__(self, time: float) -> None:
        super().__init__(time)
        self.time = time
