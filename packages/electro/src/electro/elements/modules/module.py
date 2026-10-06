"""Modules a microcontroller talks to: what each does with its signals the page emulates; here each is what it
is electrically — its load across the supply, its inputs high resistances, its own pull-ups."""

R_INPUT = 1_000_000


def load(t, vcc: str, gnd: str, r: int) -> list:
    return [t.I[vcc] - t.across(vcc, gnd) / r]


def inputs(t, pins: tuple[str, ...], gnd: str, r: int = R_INPUT) -> list:
    return [t.I[pin] - t.across(pin, gnd) / r for pin in pins]


def i2c(t, r_load: int) -> list:
    """A module on I²C: its load, and 4.7 kΩ pull-ups from SDA and SCL to its supply."""
    pull = {line: t.across(line, "vcc") / 4700 for line in ("sda", "scl")}
    return [
        t.I["sda"] - pull["sda"],
        t.I["scl"] - pull["scl"],
        t.I["vcc"] - (t.across("vcc", "gnd") / r_load - pull["sda"] - pull["scl"]),
    ]
