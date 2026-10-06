from ...circuit.element import Element


class VCCS(Element):
    """A controlled source that senses a voltage; puts out a current g times it: the control side (``cp``, ``cn``) takes no current
    (sensing a voltage) or drops no voltage (sensing a current, from ``cp`` to ``cn``); the output (``n``,
    ``p``) its + (or its current out) on ``p``."""

    kind, prefix = "vccs", "VCCS"
    terminals = ("cp", "cn", "n", "p")

    def laws(self, t, p):
        g = p[""]
        return [t.I["cp"], t.I["cp"] + t.I["cn"], -t.I["p"] - g * t.across("cp", "cn")]
