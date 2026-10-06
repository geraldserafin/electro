"""Microcontroller boards: the supplies they put out, and each I/O pin a source behind a conductance, both
set by the chip while it runs (an emulated one: ``<pin>_G``, ``<pin>_E``). On paper a pin takes nothing."""

from __future__ import annotations

import sympy as sp

from ..kind import Kind, Params, Terminals

ARDUINO_PINS = tuple(f"D{i}" for i in range(14)) + tuple(f"A{i}" for i in range(6))
PICO_PINS = tuple(f"GP{i}" for i in range(23)) + ("GP26", "GP27", "GP28")

ARDUINO_MODES = {"input": (1e-8, 0.0), "pullup": (1 / 35000, 5.0), "low": (1 / 25, 0.0), "high": (1 / 25, 5.0)}
"""What an ATmega328P makes of a pin: (conductance to the pin's source, its voltage)."""

PICO_MODES = {
    "input": (1e-8, 0.0),
    "pullup": (1 / 50000, 3.3),
    "pulldown": (1 / 50000, 0.0),
    "low": (1 / 40, 0.0),
    "high": (1 / 40, 3.3),
}
"""What an RP2040 makes of a pin: 3.3 V logic, pull-ups and pull-downs of about 50 kΩ."""


def _board(pins: tuple[str, ...], supplies: dict[str, object]):
    def laws(t: Terminals, p: Params) -> list:
        driven = [t.I[pin] - p[f"{pin}_G"] * (t.across(pin, "GND") - p[f"{pin}_E"]) for pin in pins]
        return [*driven, *(t.across(pin, "GND") - volts for pin, volts in supplies.items())]

    return laws


def _board_kind(name: str, prefix: str, pins: tuple[str, ...], supplies: dict[str, object], modes: dict) -> Kind:
    settable = tuple(f"{pin}_{x}" for pin in pins for x in ("G", "E"))
    return Kind(
        name,
        prefix,
        (*pins, *supplies, "GND"),
        _board(pins, supplies),
        parameters=settable,
        defaults=tuple((p, 0) for p in settable),
        inputs=settable,
        modes=tuple(modes.items()),
    )


Arduino = _board_kind("arduino", "ARD", ARDUINO_PINS, {"5V": 5}, ARDUINO_MODES)
"""An Arduino Uno: ``D0``–``D13``, ``A0``–``A5``, its 5 V supply."""

Pico = _board_kind("pico", "PICO", PICO_PINS, {"VBUS": 5, "3V3": sp.Rational(33, 10)}, PICO_MODES)
"""A Raspberry Pi Pico: ``GP0``–``GP22``, ``GP26``–``GP28``, its USB's ``VBUS`` and its regulator's ``3V3``."""
