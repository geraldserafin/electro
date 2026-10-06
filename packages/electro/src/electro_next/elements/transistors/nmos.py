from .mos import MOS


class NMOS(MOS):
    """An N-channel MOSFET: gate ``g``, drain ``d``, source ``s``."""

    kind = "nmos"
