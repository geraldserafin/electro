from ...element import Element
from .module import i2c


class LCD1602I2C(Element):
    """A 16×2 LCD with an I²C backpack (a PCF8574), its backlight in its load."""

    kind, prefix = "lcd1602_i2c", "LCD"
    terminals = ("gnd", "vcc", "sda", "scl")
    parameters = ()

    def laws(self, t, p):
        return i2c(t, 200)
