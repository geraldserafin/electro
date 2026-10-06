from ...element import Element
from ..diodes.light import led
from .module import inputs, load

BUS = ("rs", "rw", "e", "d0", "d1", "d2", "d3", "d4", "d5", "d6", "d7")


class LCD1602(Element):
    """An HD44780 16×2, its 16 pins in order: its logic a load, ``v0`` (contrast) and the bus inputs, its
    backlight an LED of 3 V from ``a`` to ``k``."""

    kind, prefix = "lcd1602", "LCD"
    terminals = ("vss", "vdd", "v0", *BUS, "a", "k")
    parameters = ()
    shows = (("U", ("vdd", "vss")), *((f"U_{p}", (p, "vss")) for p in ("v0", *BUS)), ("I", "vdd"))

    def laws(self, t, p):
        return [
            *load(t, "vdd", "vss", 5000),
            *inputs(t, ("v0", *BUS), "vss"),
            t.I["a"] - led(t.across("a", "k"), 3),
            t.I["vss"] + t.I["vdd"] + sum(t.I[pin] for pin in ("v0", *BUS)),
        ]
