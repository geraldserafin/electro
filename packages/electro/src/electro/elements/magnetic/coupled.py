from ...circuit.element import Element
from ...circuit.time import D
from .windings import own_loop, windings


class Coupled(Element):
    """Two inductors ``L1``, ``L2`` and their mutual inductance M (the main parameter)."""

    kind, prefix = "coupled", "M"
    terminals = ("p1", "p2", "s2", "s1")
    parameters = ("", "L1", "L2")

    def laws(self, t, p):
        u1, u2, i1, i2 = windings(t)
        M = p[""]
        return [u1 - p["L1"] * D(i1) - M * D(i2), u2 - M * D(i1) - p["L2"] * D(i2), own_loop(t)]
