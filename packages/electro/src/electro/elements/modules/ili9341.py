from ...circuit.element import Element
from .module import inputs, load


class ILI9341(Element):
    """A 2.8" 320×240 colour TFT on SPI, its pins as the module's header has them: its logic a load from
    3.3 V, the inputs high resistances, the backlight's driver 1 kΩ on ``led``."""

    kind, prefix = "ili9341", "TFT"
    terminals = ("vcc", "gnd", "cs", "reset", "dc", "mosi", "sck", "led", "miso")
    parameters = ()

    def laws(self, t, p):
        return [
            *load(t, "vcc", "gnd", 150),
            *inputs(t, ("cs", "reset", "dc", "mosi", "sck", "miso"), "gnd"),
            t.I["led"] - t.across("led", "gnd") / 1000,
        ]
