from ...element import Element


class Buzzer(Element):
    """An active buzzer (``a`` its +): it sounds above 2.5 V; electrically 160 Ω."""

    kind, prefix = "buzzer", "BZ"
    terminals = ("a", "b")
    parameters = ()

    def laws(self, t, p):
        return [t.across("a", "b") - 160 * t.I["a"]]
