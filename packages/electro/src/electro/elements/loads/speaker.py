from ...element import Element


class Speaker(Element):
    """A powered speaker (``a`` its line input, ``b`` its return): what is across it is heard, its DC not
    (the amplifier's input is AC-coupled); electrically 10 kΩ."""

    kind, prefix = "speaker", "LS"
    terminals = ("a", "b")
    parameters = ()

    def laws(self, t, p):
        return [t.across("a", "b") - 10000 * t.I["a"]]
