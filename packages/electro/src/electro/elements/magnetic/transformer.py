from ...circuit.element import Element
from ...circuit.time import D
from .windings import own_loop, windings


class Transformer(Element):
    """Of ratio n (U₁ = n·U₂): each winding sees the flux change, the secondary 1/n of it; what the windings'
    currents leave over magnetizes the core (``L_m``, large). In DC a winding is a short. The primary ``p1``
    (its dot), ``p2``; the secondary ``s1`` (its dot), ``s2``."""

    kind, prefix = "transformer", "TR"
    terminals = ("p1", "p2", "s2", "s1")
    parameters = ("", "L_m")
    defaults = {"L_m": 10**6}

    def laws(self, t, p):
        u1, u2, i1, i2 = windings(t)
        n, flux = p[""], t.inner("flux")
        return [u1 - D(flux), n * u2 - D(flux), flux - p["L_m"] * (i1 + i2 / n), own_loop(t)]
