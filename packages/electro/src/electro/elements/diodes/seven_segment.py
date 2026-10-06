from ...element import Element
from .light import led

SEGMENTS = ("a", "b", "c", "d", "e", "f", "g", "dp")


class SevenSegment(Element):
    """A digit (a 5161AS): red segments ``a``–``g`` and the dot ``dp``, a common cathode ``com``."""

    kind, prefix = "seven_segment", "DS"
    terminals = (*SEGMENTS, "com")
    parameters = ()

    def laws(self, t, p):
        return [t.I[pin] - led(t.across(pin, "com"), 2) for pin in SEGMENTS]
