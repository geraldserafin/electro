import sympy as sp

from ...element import Element
from ...time import TIME


class SineSource(Element):
    """E·sin(2π·f·t + φ), φ in degrees, its + on its second end. In AC it is the phasor E∠φ."""

    kind, prefix = "sine_source", "E"
    terminals = ("a", "b")
    parameters = ("", "f", "phase")
    defaults = {"f": 50, "phase": 0}

    def laws(self, t, p):
        return [t.across("a", "b") + p[""] * sp.sin(2 * sp.pi * p["f"] * TIME + sp.pi * p["phase"] / 180)]
