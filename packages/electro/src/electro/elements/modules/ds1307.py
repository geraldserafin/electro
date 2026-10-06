from ...circuit.element import Element
from .module import i2c


class DS1307(Element):
    """A real-time clock on I²C."""

    kind, prefix = "ds1307", "RTC"
    terminals = ("gnd", "vcc", "sda", "scl")
    parameters = ()

    def laws(self, t, p):
        return i2c(t, 3300)
