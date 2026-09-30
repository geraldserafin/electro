"""What can go wrong with a drawing, as types (like ``electro.issues``: data, no sentences)."""

from __future__ import annotations

from electro.issues import Issue, issue


class Unsupported(Issue, NotImplementedError):
    """A circuit from code that layout() cannot draw (yet): draw it on the grid instead."""


@issue
class CannotLayOut(Unsupported):
    """A kind of circuit layout() does not know (it knows two-terminal elements, +, |, shunt,
    transpose, close/loop, node, ground, wire)."""

    circuit: str


@issue
class CannotLayOutElement(Unsupported):
    """An element that is not 1 → 1."""

    element: str
    shape: str


@issue
class CannotLayOutParallel(Unsupported):
    shape: str


@issue
class CannotLayOutLoop(Unsupported):
    shape: str


@issue
class NoKindFor(Issue, KeyError):
    """A component class with no kind in KINDS (a gap in the library, not the user's mistake)."""

    component: str


@issue
class UnknownKind(Issue, ValueError):
    kind: str
    available: list


@issue
class BadRotation(Issue, ValueError):
    """Rotations are multiples of 90°."""

    rotation: int


@issue
class SkewedWire(Issue, ValueError):
    """A wire's segment that is neither horizontal nor vertical."""

    start: tuple
    end: tuple


@issue
class NotOnSchematic(Issue, KeyError):
    id: str


@issue
class EmptySchematic(Issue, ValueError):
    pass


@issue
class UnknownPart(Issue, KeyError):
    """An element of one's own components (kind "part") whose definition the drawing does not have."""

    part: str


@issue
class PartInItself(Issue, ValueError):
    """A component that has itself inside (at some depth): it would never end."""

    part: str
