"""Modules a microcontroller talks to: a distance sensor, character and graphic displays, a clock. What
each does with its signals the page emulates; here each is what it is electrically: its load across the
supply, its inputs high resistances, its own pull-ups, an LED for a backlight."""

from __future__ import annotations

from ..kind import Kind, Params, Terminals
from .diodes import led

LCD_INPUTS = ("rs", "rw", "e", "d0", "d1", "d2", "d3", "d4", "d5", "d6", "d7")
R_INPUT = 1_000_000


def _load(t: Terminals, vcc: str, gnd: str, r: int) -> list:
    return [t.I[vcc] - t.across(vcc, gnd) / r]


def _inputs(t: Terminals, pins: tuple[str, ...], gnd: str, r: int = R_INPUT) -> list:
    return [t.I[pin] - t.across(pin, gnd) / r for pin in pins]


def _ultrasonic(t: Terminals, p: Params) -> list:
    """An HC-SR04: ``echo`` a source of ``vcc`` (``echo`` set to 1 while the sound is on its way back) or
    0 V behind 100 Ω; ``trig`` an input."""
    echo = (t.across("echo", "gnd") - p["echo"] * t.across("vcc", "gnd")) / 100
    return [*_load(t, "vcc", "gnd", 333), *_inputs(t, ("trig",), "gnd", 100_000), t.I["echo"] - echo]


def _lcd(t: Terminals, _: Params) -> list:
    """An HD44780 16×2: its logic a load, ``v0`` (contrast) and the bus inputs, its backlight an LED of 3 V
    from ``a`` to ``k``."""
    return [
        *_load(t, "vdd", "vss", 5000),
        *_inputs(t, ("v0", *LCD_INPUTS), "vss"),
        t.I["a"] - led(t.across("a", "k"), 3),
        t.I["vss"] + t.I["vdd"] + sum(t.I[pin] for pin in ("v0", *LCD_INPUTS)),
    ]


def _i2c(r_load: int):
    """A module on I²C: its load, and 4.7 kΩ pull-ups from SDA and SCL to its supply."""

    def laws(t: Terminals, _: Params) -> list:
        pull = {line: t.across(line, "vcc") / 4700 for line in ("sda", "scl")}
        return [
            t.I["sda"] - pull["sda"],
            t.I["scl"] - pull["scl"],
            t.I["vcc"] - (t.across("vcc", "gnd") / r_load - pull["sda"] - pull["scl"]),
        ]

    return laws


def _tft(t: Terminals, _: Params) -> list:
    """An ILI9341 on SPI: its logic a load from 3.3 V, the inputs high resistances, the backlight's driver
    1 kΩ on ``led``."""
    return [
        *_load(t, "vcc", "gnd", 150),
        *_inputs(t, ("cs", "reset", "dc", "mosi", "sck", "miso"), "gnd"),
        t.I["led"] - t.across("led", "gnd") / 1000,
    ]


Ultrasonic = Kind(
    "ultrasonic",
    "US",
    ("vcc", "trig", "echo", "gnd"),
    _ultrasonic,
    parameters=("echo",),
    defaults=(("echo", 0),),
    inputs=("echo",),
    shows=(("U", ("vcc", "gnd")), ("U_trig", ("trig", "gnd")), ("I", "vcc")),
)

LCD1602 = Kind(
    "lcd1602",
    "LCD",
    ("vss", "vdd", "v0", *LCD_INPUTS, "a", "k"),
    _lcd,
    parameters=(),
    shows=(("U", ("vdd", "vss")), *((f"U_{p}", (p, "vss")) for p in ("v0", *LCD_INPUTS)), ("I", "vdd")),
)
"""Its 16 pins in order."""

LCD1602I2C = Kind("lcd1602_i2c", "LCD", ("gnd", "vcc", "sda", "scl"), _i2c(200), parameters=())
"""With an I²C backpack (a PCF8574), its backlight in its load."""

SSD1306 = Kind("ssd1306", "OLED", ("gnd", "vcc", "scl", "sda"), _i2c(250), parameters=())
"""A 0.96" 128×64 OLED."""

DS1307 = Kind("ds1307", "RTC", ("gnd", "vcc", "sda", "scl"), _i2c(3300), parameters=())
"""A real-time clock."""

ILI9341 = Kind("ili9341", "TFT", ("vcc", "gnd", "cs", "reset", "dc", "mosi", "sck", "led", "miso"), _tft, parameters=())
"""A 2.8" 320×240 colour TFT, its pins as the module's header has them."""

I2C_ADDRESSES = {"lcd1602_i2c": (0x27, 0x3F), "ssd1306": (0x3C, 0x3D), "ds1307": (0x68,)}
"""The addresses a module may be set to, the first as it comes."""
