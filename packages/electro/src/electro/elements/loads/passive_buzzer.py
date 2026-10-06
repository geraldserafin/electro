from ...circuit.element import Element


class PassiveBuzzer(Element):
    """A passive buzzer: it sounds at what drives it; electrically its coil, 16 Ω."""

    kind, prefix = "passive_buzzer", "BZ"
    terminals = ("a", "b")
    parameters = ()

    def laws(self, t, p):
        return [t.across("a", "b") - 16 * t.I["a"]]
