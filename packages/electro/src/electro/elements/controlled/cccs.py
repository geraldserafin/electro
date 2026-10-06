from ...element import Element


class CCCS(Element):
    """A controlled source that senses a current; puts out a current k times it: the control side (``cp``, ``cn``) takes no current
    (sensing a voltage) or drops no voltage (sensing a current, from ``cp`` to ``cn``); the output (``n``,
    ``p``) its + (or its current out) on ``p``."""

    kind, prefix = "cccs", "CCCS"
    terminals = ("cp", "cn", "n", "p")

    def laws(self, t, p):
        g = p[""]
        return [t.across("cp", "cn"), t.I["cp"] + t.I["cn"], -t.I["p"] - g * t.I["cp"]]
