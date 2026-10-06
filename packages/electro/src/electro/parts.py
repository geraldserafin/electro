"""Real parts by name: a kind's parameters as its maker gives them (an LED's colour: its forward voltage)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

DIODE_PARTS = {"1N4148": {"I_S": 2.52e-9, "n": 1.752}, "1N4007": {"I_S": 76.9e-12, "n": 1.45}}
"""Real diodes' parameters, as their makers' SPICE models have them."""

LED_COLORS = {"red": 2, "orange": 2.05, "yellow": 2.1, "green": 2.2, "blue": 3.1, "white": 3.2}
"""An LED's forward voltage at 20 mA by its colour."""

BJT_PARTS = {
    "BC547B": {"IS": 2.39e-14, "BF": 294.3, "BR": 7.946},
    "2N2222": {"IS": 14.34e-15, "BF": 255.9, "BR": 6.092},
    "2N3904": {"IS": 6.734e-15, "BF": 416.4, "BR": 0.7371},
    "BC557B": {"IS": 3.83e-14, "BF": 344.4, "BR": 14.84},
    "2N3906": {"IS": 1.41e-15, "BF": 180.7, "BR": 4.977},
}
"""Ebers–Moll as their makers' SPICE models give it (saturation current, gains forward and reverse)."""

OPAMP_PARTS = {
    "LM358": {"A": 1e5, "GBW": 1e6, "SR": 0.3e6, "LOW": -15.0, "HIGH": 13.5},
    "TL072": {"A": 2e5, "GBW": 3e6, "SR": 13e6, "LOW": -13.5, "HIGH": 13.5},
    "MCP6002": {"A": 4e5, "GBW": 1e6, "SR": 0.6e6, "LOW": 0.0, "HIGH": 5.0},
}
"""Real op-amps: gain, gain-bandwidth (Hz), slew rate (V/s), the rails its output reaches on its usual
supply."""

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
