"""How elements look: one symbol library for the Python renderer and the web editor.

Each symbol is SVG drawn at rotation 0 with the element's first pin at (0, 0), in
pixels (``GRID`` px per grid unit). Pins come from ``electro_schematic.KINDS``.
``symbol_library()`` exports everything as JSON-friendly data for the web editor.
"""

from __future__ import annotations

import json

from electro_schematic import GRID, KINDS

def _body(inner: str, half: float = 20) -> str:
    """A two-pin symbol: leads from both pins up to the body, ``half`` px either side of the middle."""
    return f'<path d="M0 0H{40 - half:g}M{40 + half:g} 0H80"/><g transform="translate(40 0)">{inner}</g>'


SYMBOLS: dict[str, str] = {
    "resistor": _body('<rect x="-18" y="-7" width="36" height="14"/>', 18),
    "capacitor": _body('<path d="M-20 0H-4M4 0H20"/><path class="thick" d="M-4 -12V12M4 -12V12"/>'),
    "inductor": _body('<path d="M-20 0' + "a5 5 0 0 1 10 0" * 4 + '"/>'),
    "voltage_source": _body('<circle r="13"/><path d="M-13 0H13"/><path class="fill" d="M13 0l-7 -4v8z"/>', 13),
    "current_source": _body('<circle r="13"/><path d="M0 -13V13"/><path class="fill" d="M24 0l-8 -4.5v9z"/>', 13),
    "ammeter": _body('<circle r="13"/>', 13),
    "voltmeter": _body('<circle r="13"/>', 13),
    "hole": _body('<rect class="dashed" x="-18" y="-10" width="36" height="20"/>', 18),
    "opamp": '<path d="M0 0H20M0 40H20M60 20H80"/><path d="M20 -10L20 50L62 20Z"/>'
             '<path d="M24 0h7M24 40h7M27.5 36.5v7"/>',
    "ground": '<path d="M0 0v10M-11 10h22M-7 14h14M-3 18h6"/>',
    "label": "",
    "terminal": '<circle class="open" r="3.5"/>',
}

# Letters stay upright, so they are drawn apart from the (rotating) symbol.
LETTERS = {"ammeter": "A", "voltmeter": "V", "hole": "?"}

# Symbols that always point down on the page, whatever the element's rotation.
UPRIGHT = {"ground", "label", "terminal"}

STYLE = """
.w{stroke:currentColor;stroke-width:1.6;fill:none;stroke-linecap:round;stroke-linejoin:round}
.w .thick{stroke-width:3}.w .fill{fill:currentColor;stroke:none}.w .dashed{stroke-dasharray:4 3}
.w .open{fill:none}.dot{fill:currentColor}
text{font:13px ui-sans-serif,system-ui,sans-serif;fill:currentColor}.halo{fill:var(--paper,#fff)}
text .sub{font-size:10px}.solved{fill:#2563eb;font-weight:600}.result{fill:#059669}
.node{font-style:italic}.letter{font-weight:600;text-anchor:middle;dominant-baseline:central}
"""


def symbol_library() -> dict:
    """Everything an editor needs to draw elements exactly like the renderer does."""
    return {
        "grid": GRID,
        "style": STYLE,
        "kinds": {
            kind: {
                "pins": [[x * GRID, y * GRID] for x, y in KINDS[kind].pins],
                "svg": SYMBOLS[kind],
                "letter": LETTERS.get(kind),
                "upright": kind in UPRIGHT,
            }
            for kind in KINDS
        },
    }


def symbol_library_json() -> str:
    return json.dumps(symbol_library(), ensure_ascii=False)
