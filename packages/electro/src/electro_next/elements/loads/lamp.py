from ...element import Element


class Lamp(Element):
    """An incandescent bulb: its filament, hot, a resistor (the main parameter)."""

    kind, prefix = "lamp", "H"
    terminals = ("a", "b")
    positive = ("",)

    def laws(self, t, p):
        return [t.across("a", "b") - p[""] * t.I["a"]]
