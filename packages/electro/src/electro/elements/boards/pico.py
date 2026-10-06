import sympy as sp

from .board import Board


class Pico(Board):
    """A Raspberry Pi Pico: ``GP0``–``GP22``, ``GP26``–``GP28``, its USB's ``VBUS`` and its regulator's ``3V3``.
    An RP2040's pin modes: 3.3 V logic, pull-ups and pull-downs of about 50 kΩ."""

    kind, prefix = "pico", "PICO"
    pins = tuple(f"GP{i}" for i in range(23)) + ("GP26", "GP27", "GP28")
    supplies = {"VBUS": 5, "3V3": sp.Rational(33, 10)}
    modes = {
        "input": (1e-8, 0.0),
        "pullup": (1 / 50000, 3.3),
        "pulldown": (1 / 50000, 0.0),
        "low": (1 / 40, 0.0),
        "high": (1 / 40, 3.3),
    }
