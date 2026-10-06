from .mos import MOS


class PMOS(MOS):
    """A P-channel MOSFET: an NMOS with every voltage and current the other way."""

    kind = "pmos"
    polarity = -1
