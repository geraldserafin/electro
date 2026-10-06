from ...circuit.element import Element
from .light import led


class LED(Element):
    """A light-emitting diode: its main parameter its forward voltage at 20 mA (red, 2 V, unless given)."""

    kind, prefix = "led", "LED"
    terminals = ("a", "b")
    defaults = {"": 2}

    def laws(self, t, p):
        return [t.I["a"] - led(t.across("a", "b"), p[""])]
