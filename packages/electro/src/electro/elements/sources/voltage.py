from ...circuit.element import Element


class VoltageSource(Element):
    """Its + on its second end: V_b − V_a = E."""

    kind, prefix = "voltage_source", "E"
    terminals = ("a", "b")

    def laws(self, t, p):
        return [t.across("a", "b") + p[""]]
