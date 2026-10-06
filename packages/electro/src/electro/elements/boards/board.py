"""A microcontroller board: the supplies it puts out, and each I/O pin a source behind a conductance, both set
by the chip while it runs (an emulated one: ``<pin>_G``, ``<pin>_E``). On paper a pin takes nothing."""

from ...circuit.element import Element


class Board(Element):
    pins: tuple[str, ...] = ()
    supplies: dict[str, object] = {}

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        settable = tuple(f"{pin}_{x}" for pin in cls.pins for x in ("G", "E"))
        cls.terminals = (*cls.pins, *cls.supplies, "GND")
        cls.parameters = cls.inputs = settable
        cls.defaults = dict.fromkeys(settable, 0)

    def laws(self, t, p):
        driven = [t.I[pin] - p[f"{pin}_G"] * (t.across(pin, "GND") - p[f"{pin}_E"]) for pin in self.pins]
        return [*driven, *(t.across(pin, "GND") - volts for pin, volts in self.supplies.items())]
