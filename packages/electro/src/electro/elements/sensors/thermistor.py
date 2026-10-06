import sympy as sp

from ...circuit.element import Element

B, KELVIN = 3950, sp.Rational(27315, 100)


class Thermistor(Element):
    """An NTC's: R·e^(B·(1/T − 1/T₂₅)); its main parameter its resistance at 25 °C, ``temperature`` in °C."""

    kind, prefix = "thermistor", "RT"
    terminals = ("a", "b")
    parameters = ("", "temperature")
    defaults = {"temperature": 25}
    positive = ("",)
    inputs = ("temperature",)

    def laws(self, t, p):
        factor = sp.exp(B * (1 / (p["temperature"] + KELVIN) - 1 / (25 + KELVIN)))
        return [t.across("a", "b") - p[""] * factor * t.I["a"]]
