from .bipolar import Bipolar


class NPN(Bipolar):
    """An NPN transistor: base ``b``, collector ``c``, emitter ``e``."""

    kind = "npn"
