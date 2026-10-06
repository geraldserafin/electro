from .switch import Switch


class Button(Switch):
    """Closed while pressed."""

    kind, prefix = "button", "B"
