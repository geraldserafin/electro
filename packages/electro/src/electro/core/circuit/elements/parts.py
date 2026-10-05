"""Real parts by name: a kind's parameters as its maker gives them (an LED's colour: its forward voltage)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .chips import OPAMP_PARTS
from .diodes import DIODE_PARTS, LED_COLORS
from .transistors import BJT_PARTS

CATALOGUE: dict[str, Mapping[str, Mapping[str, object]]] = {
    "diode": DIODE_PARTS,
    "npn": BJT_PARTS,
    "pnp": BJT_PARTS,
    "opamp_model": OPAMP_PARTS,
    "led": {color: {"": v} for color, v in LED_COLORS.items()},
}


class UnknownPart(KeyError):
    def __init__(self, part: str, available: list[str]) -> None:
        super().__init__(part)
        self.part, self.available = part, available


@dataclass(frozen=True)
class Part:
    """A real part as an element's value: ``part("1N4148")``, ``part("blue")``."""

    name: str

    def parameters(self, kind: str) -> dict[str, object]:
        catalogue = CATALOGUE.get(kind, {})
        if self.name not in catalogue:
            raise UnknownPart(self.name, sorted(catalogue))
        return dict(catalogue[self.name])


def part(name: str) -> Part:
    return Part(name)
