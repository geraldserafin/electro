from ...element import Element
from .module import inputs, load

R_OUT = 1
"""Its output buffer's resistance (Ω)."""


class MCP4822(Element):
    """A dual 12-bit DAC on SPI (Microchip MCP4822, 2.048 V reference): its logic a load from ``vdd``, the inputs
    high resistances, each output a source behind its buffer, at what the program last sent it (``A``, ``B``:
    volts, set by the page as the words come)."""

    kind, prefix = "mcp4822", "DAC"
    terminals = ("vdd", "cs", "sck", "sdi", "ldac", "vouta", "voutb", "gnd")
    parameters = ("A", "B")
    inputs = ("A", "B")
    defaults = {"A": 0, "B": 0}

    def laws(self, t, p):
        return [
            *load(t, "vdd", "gnd", 10000),
            *inputs(t, ("cs", "sck", "sdi", "ldac"), "gnd"),
            *(t.I[out] - (t.across(out, "gnd") - p[ch]) / R_OUT for out, ch in (("vouta", "A"), ("voutb", "B"))),
        ]
