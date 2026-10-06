from .board import Board


class Arduino(Board):
    """An Arduino Uno: ``D0``–``D13``, ``A0``–``A5``, its 5 V supply. An ATmega328P's pin modes: (conductance to
    the pin's source, its voltage)."""

    kind, prefix = "arduino", "ARD"
    pins = tuple(f"D{i}" for i in range(14)) + tuple(f"A{i}" for i in range(6))
    supplies = {"5V": 5}
    modes = {"input": (1e-8, 0.0), "pullup": (1 / 35000, 5.0), "low": (1 / 25, 0.0), "high": (1 / 25, 5.0)}
