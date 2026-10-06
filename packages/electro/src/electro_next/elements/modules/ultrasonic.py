from ...element import Element
from .module import inputs, load


class Ultrasonic(Element):
    """An HC-SR04: ``echo`` a source of ``vcc`` (``echo`` set to 1 while the sound is on its way back) or 0 V
    behind 100 Ω; ``trig`` an input."""

    kind, prefix = "ultrasonic", "US"
    terminals = ("vcc", "trig", "echo", "gnd")
    parameters = ("echo",)
    defaults = {"echo": 0}
    inputs = ("echo",)
    shows = (("U", ("vcc", "gnd")), ("U_trig", ("trig", "gnd")), ("I", "vcc"))

    def laws(self, t, p):
        echo = (t.across("echo", "gnd") - p["echo"] * t.across("vcc", "gnd")) / 100
        return [*load(t, "vcc", "gnd", 333), *inputs(t, ("trig",), "gnd", 100_000), t.I["echo"] - echo]
