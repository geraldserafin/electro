from .bipolar import Bipolar


class PNP(Bipolar):
    """A PNP transistor: an NPN with every voltage and current the other way."""

    kind = "pnp"
    polarity = -1
