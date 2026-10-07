import sympy as sp

from ...element import Element
from ...parts import OPAMP_PARTS
from ...time import D

R_OUT = 75


class OpAmpModel(Element):
    """A real op-amp (``OPAMP_PARTS``; an LM358 unless given): gain ``A`` with one pole at ``GBW``, the output
    (``y``, behind ``R_OUT``) moving at most at ``SR`` and never past its rails ``LOW``, ``HIGH`` (against its
    supply's return, ``gnd``, not drawn)."""

    kind, prefix = "opamp_model", "OA"
    terminals = ("plus", "minus", "out", "gnd")
    parameters = ("A", "GBW", "SR", "LOW", "HIGH")
    defaults = OPAMP_PARTS["LM358"]
    ground = True

    def laws(self, t, p):
        y = t.inner("y")
        tau = p["A"] / (2 * sp.pi * p["GBW"])
        drive = (p["A"] * t.across("plus", "minus") - y) / tau
        slope = p["SR"] * sp.tanh(drive / p["SR"])
        below_top, above_bottom = (1 - sp.tanh(20 * (y - p["HIGH"]))) / 2, (1 + sp.tanh(20 * (y - p["LOW"]))) / 2
        rising = (1 + sp.tanh(slope / 1000)) / 2
        return [
            t.I["plus"],
            t.I["minus"],
            D(y) - slope * (rising * below_top + (1 - rising) * above_bottom),
            t.I["out"] - (t.across("out", "gnd") - y) / R_OUT,
        ]
