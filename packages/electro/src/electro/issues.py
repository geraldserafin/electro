"""What can go wrong, as types: each case is its own class holding the data that says which —
never a sentence. Whoever shows an issue says it (the notebook: in the reader's language), so
``str()`` is only the repr.

Each one also subclasses the built-in error it stands for (``KeyError``, ``TypeError``, …),
so ``except TypeError`` keeps catching it. ``Underdetermined`` is a warning (``UserWarning``).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import sympy as sp


class Issue(Exception):
    """An error (or a warning) as data."""

    def __str__(self) -> str:
        return repr(self)


def issue(cls):
    """A dataclass that stays an exception (compared by identity, like any)."""
    return dataclass(eq=False)(cls)


# ------------------------------------------------------------------ pieces of data in issues

@dataclass(frozen=True)
class Equals:
    """A quantity and its value: ``I_R_1 = 0.5 A``."""

    symbol: sp.Symbol
    value: sp.Expr
    unit: str = ""


@dataclass(frozen=True)
class IsZero:
    """A condition that is not a single value: ``U_R_1 - 2·U_R_2 = 0``."""

    expr: sp.Expr


# ------------------------------------------------------------------ solving

class CircuitError(Issue):
    """The circuit cannot be solved as asked."""


class Contradiction(CircuitError):
    """The data are inconsistent with the circuit."""


@issue
class ConflictingData(Contradiction):
    """Which data clash: removing any one of them makes the rest consistent. Conditions (given
    to solve()) and values (of the elements) are ``Equals`` / ``IsZero``; both empty: no single
    change fixes it. ``cause``: the contradiction the solver met first."""

    conditions: list
    values: list
    cause: Contradiction | None = field(default=None, repr=False, metadata={"shown": False})


@issue
class LawBroken(Contradiction):
    """A law with nothing unknown left in it does not hold: it leaves ``rest`` ≠ 0."""

    law: object  # components.Law
    rest: sp.Expr


@issue
class NoSolutionFor(Contradiction):
    """A law leaves no admissible value for ``variable`` (e.g. a negative resistance)."""

    variable: sp.Symbol
    law: object


@issue
class NoSystemSolution(Contradiction):
    """The equations left after propagation have no common solution."""

    laws: list


@issue
class Ambiguous(CircuitError):
    """More than one solution (nonlinear laws): each option is a list of ``Equals``."""

    options: list


@issue
class MissingData(CircuitError):
    """What was asked for is not determined. ``needed``: how many more independent data (None:
    more than searched for); ``options``: minimal sets of quantities that would do. ``solution``
    holds what was found."""

    targets: list
    needed: int | None
    options: list
    solution: object = field(default=None, repr=False, metadata={"shown": False})


@issue
class Underdetermined(Issue, UserWarning):
    """A warning: not everything in the circuit is determined (what MissingData says)."""

    targets: list
    needed: int | None
    options: list


@issue
class Undetermined(CircuitError):
    """An expression asked of a solution uses quantities it did not determine."""

    symbols: list


@issue
class HoleUndetermined(CircuitError):
    """What an unknown element (a hole) is could not be decided."""

    label: sp.Symbol


@issue
class BadCondition(Issue, TypeError):
    """A condition passed to solve() that is neither ``{quantity: value}`` nor ``Eq(...)``."""

    condition: str


# ------------------------------------------------------------------ finding things

@issue
class NotInCircuit(Issue, KeyError):
    """A component (object or label) that is not in the solved circuit."""

    name: str


@issue
class ComponentRepeated(Issue, KeyError):
    """The same component object is placed ``count`` times: ask by label."""

    count: int


@issue
class NoSuchQuantity(Issue, KeyError):
    name: str
    available: list


@issue
class NoSuchElement(Issue, KeyError):
    label: str
    available: list


@issue
class DuplicateLabel(Issue, ValueError):
    label: sp.Symbol


# ------------------------------------------------------------------ values

@issue
class BadValue(Issue, ValueError):
    """Text that is not a value (examples of ones that are: 10, 4.7, '4.7k', '4k7', '0,5 A', 'R')."""

    value: str


@issue
class NotAValue(Issue, TypeError):
    """An object of a type no value is made of."""

    value: str


# ------------------------------------------------------------------ building circuits

@issue
class NotACircuit(Issue, TypeError):
    value: str


@issue
class SeriesMismatch(Issue, TypeError):
    """``left + right``: left has ``outputs`` terminals on its right, right ``inputs`` on its left."""

    left: str
    right: str
    outputs: int
    inputs: int


@issue
class ParallelMismatch(Issue, TypeError):
    """``a | b`` needs parts of one shape (``1 → 1``, …)."""

    first: str
    first_shape: str
    other: str
    other_shape: str


@issue
class ShuntNeedsOneToOne(Issue, TypeError):
    part: str
    shape: str  # a circuit's shape: "2 → 1" (its ``type``)


@issue
class CloseNeedsNToN(Issue, TypeError):
    shape: str


@issue
class WrongNodeCount(Issue, TypeError):
    """``net(...)``: a part with ``terminals`` terminals given the nodes ``nodes``."""

    part: str
    terminals: int
    nodes: list


# ------------------------------------------------------------------ analysis

@issue
class NotLinear(Issue, ValueError):
    """blackbox() works for linear circuits only."""


@issue
class NotAPort(Issue, TypeError):
    """equivalent() needs a 1 → 1 circuit, or 0 → 1 (against ground)."""

    shape: str


@issue
class NoThevenin(Issue, ValueError):
    """The terminals are open (R_th = ∞): there is no Thévenin equivalent."""


# ------------------------------------------------------------------ simulation in time

@issue
class NeedsSimulation(Issue, ValueError):
    """``label`` is not linear (a diode, a transistor, a chip): the circuit is simulated in time
    (``simulate(...)``), not solved on paper."""

    label: sp.Symbol


@issue
class NotSimulated(Issue, ValueError):
    """``label`` has no model in time (a hole: the simulation needs every element known)."""

    label: sp.Symbol


@issue
class ValueNeeded(Issue, ValueError):
    """A simulation needs every value: ``label``'s is unknown."""

    label: sp.Symbol


@issue
class NoConvergence(Issue, ArithmeticError):
    """The simulation could not find the circuit's state at ``time`` (seconds), even in tiny steps."""

    time: float


@issue
class NoSuchInput(Issue, KeyError):
    """Nothing in the circuit is set from outside by that name (a switch's ``S_1``, an Arduino's pin)."""

    name: str
    available: list
