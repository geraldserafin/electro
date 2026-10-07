from ...element import Element


class VCVS(Element):
    """A controlled source that senses a voltage; puts out a voltage μ times it: the control side (``cp``, ``cn``) takes no current
    (sensing a voltage) or drops no voltage (sensing a current, from ``cp`` to ``cn``); the output (``n``,
    ``p``) its + (or its current out) on ``p``."""

    kind, prefix = "vcvs", "VCVS"
    terminals = ("cp", "cn", "n", "p")

    def laws(self, t, p):
        g = p[""]
        return [t.I["cp"], t.I["cp"] + t.I["cn"], t.across("p", "n") - g * t.across("cp", "cn")]
