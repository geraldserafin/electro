from ...element import Element


class Servo(Element):
    """A hobby servo: its angle follows the pulses on ``sig`` (the page reads them); its signal input a high
    resistance, its motor at rest a resistor across the supply."""

    kind, prefix = "servo", "M"
    terminals = ("sig", "vcc", "gnd")
    parameters = ()
    shows = (("U_sig", ("sig", "gnd")), ("U", ("vcc", "gnd")), ("I", "vcc"))

    def laws(self, t, p):
        return [t.I["sig"] - t.across("sig", "gnd") / 100_000, t.I["vcc"] - t.across("vcc", "gnd") / 500]
