from ...circuit.element import Element
from .module import i2c


class SSD1306(Element):
    """A 0.96" 128×64 OLED on I²C."""

    kind, prefix = "ssd1306", "OLED"
    terminals = ("gnd", "vcc", "scl", "sda")
    parameters = ()

    def laws(self, t, p):
        return i2c(t, 250)
