"""How elements look: one symbol library for the Python renderer and the web editor.

Two standards, chosen per note: IEC 60617 (PN-EN 60617 — a resistor is a box, a source a circle
with its arrow; the default) and IEEE Std 315 / ANSI Y32.2 (a resistor is a zigzag, a DC voltage
source a cell — its long plate the + terminal —, a current source a circle with the current's
arrow inside). ``SYMBOLS`` are IEC's; ``IEEE`` the symbols IEEE draws otherwise (the rest are the
same in both). ``use()`` picks the one the renderer draws with.

Each symbol is SVG drawn at rotation 0 with the element's first pin at (0, 0), in
pixels (``GRID`` px per grid unit). Pins come from ``electro_schematic.KINDS``.
``symbol_library()`` exports everything as JSON-friendly data for the web editor.
"""

from __future__ import annotations

import json

from electro_schematic import GRID, KINDS

# a zigzag between x = -18 and 18: three full teeth, 7 px high (a resistor, a potentiometer's body)
ZIGZAG = '<path d="M-18 0L-15 -7L-9 7L-3 -7L3 7L9 -7L15 7L18 0"/>'


def _body(inner: str, half: float = 20) -> str:
    """A two-pin symbol: leads from both pins up to the body, ``half`` px either side of the middle."""
    return f'<path d="M0 0H{40 - half:g}M{40 + half:g} 0H80"/><g transform="translate(40 0)">{inner}</g>'


SYMBOLS: dict[str, str] = {
    "resistor": _body('<rect x="-18" y="-7" width="36" height="14"/>', 18),
    "capacitor": _body('<path d="M-20 0H-4M4 0H20"/><path class="thick" d="M-4 -12V12M4 -12V12"/>'),
    "inductor": _body('<path d="M-20 0' + "a5 5 0 0 1 10 0" * 4 + '"/>'),
    "voltage_source": _body('<circle r="13"/><path d="M-13 0H13"/><path class="fill" d="M13 0l-7 -4v8z"/>', 13),
    "current_source": _body('<circle r="13"/><path d="M0 -13V13"/><path class="fill" d="M24 0l-8 -4.5v9z"/>', 13),
    # a sine / a square wave in the circle, + by the right terminal
    "sine_source": _body('<circle r="13"/><path d="M-8 0C-5.5 -9 -2.5 -9 0 0S5.5 9 8 0"/><path d="M20 -13h6M23 -16v6"/>', 13),
    "square_source": _body('<circle r="13"/><path d="M-8 5H-4V-5H4V5H8"/><path d="M20 -13h6M23 -16v6"/>', 13),
    "ammeter": _body('<circle r="13"/>', 13),
    "voltmeter": _body('<circle r="13"/>', 13),
    # controlled sources: a diamond, + inside for a voltage, an arrow for a current; the control side
    # two open terminals (a voltage sensed) or a branch with the current's arrow (a current sensed)
    "vcvs": '<path d="M0 0H14M0 80H14"/><path d="M20 0h8M24 -4v8M20 80h8"/><path d="M80 0V24M80 56V80M80 24L96 40L80 56L64 40Z"/><path d="M76 34h8M80 30v8M76 47h8"/>',
    "vccs": '<path d="M0 0H14M0 80H14"/><path d="M20 0h8M24 -4v8M20 80h8"/><path d="M80 0V24M80 56V80M80 24L96 40L80 56L64 40Z"/><path d="M80 51V38"/><path class="fill" d="M80 31l-4 7h8z"/>',
    "ccvs": '<path d="M0 0V80"/><path class="fill" d="M0 46l-4.5 -8h9z"/><path d="M80 0V24M80 56V80M80 24L96 40L80 56L64 40Z"/><path d="M76 34h8M80 30v8M76 47h8"/>',
    "cccs": '<path d="M0 0V80"/><path class="fill" d="M0 46l-4.5 -8h9z"/><path d="M80 0V24M80 56V80M80 24L96 40L80 56L64 40Z"/><path d="M80 51V38"/><path class="fill" d="M80 31l-4 7h8z"/>',
    "hole": _body('<rect class="dashed" x="-18" y="-10" width="36" height="20"/>', 18),
    "opamp": '<path d="M0 0H20M0 40H20M60 20H80"/><path d="M20 -10L20 50L62 20Z"/>'
             '<path d="M24 0h7M24 40h7M27.5 36.5v7"/>',
    "diode": _body('<path d="M-8 -9L8 0L-8 9Z"/><path d="M8 -9V9"/>', 8),
    "zener": _body('<path d="M-8 -9L8 0L-8 9Z"/><path d="M4 -11L8 -9V9L12 11"/>', 8),  # the bar's ends bent: Z
    "led": _body('<path d="M-8 -9L8 0L-8 9Z"/><path d="M8 -9V9"/>'
                 '<path d="M0 -13l7 -8M6 -15l7 -8"/><path class="fill" d="M9 -23.5l-4.5 1.3l3.2 2.8zM15 -25.5l-4.5 1.3l3.2 2.8z"/>', 8),
    # a switch or a button drawn open; closed (class "closed" on it, or on the element around it) as it then is
    "switch": _body('<circle class="open" cx="-12" r="2.5"/><circle class="open" cx="12" r="2.5"/>'
                    '<path class="when-open" d="M-10 -1.5L11 -12"/><path class="when-closed" d="M-10 -1.5L10 -1.5"/>', 14.5),
    "button": _body('<circle class="open" cx="-12" r="2.5"/><circle class="open" cx="12" r="2.5"/>'
                    '<path class="when-open" d="M-15 -7H15M0 -7V-16M-5 -16H5"/>'
                    '<path class="when-closed" d="M-15 -2.5H15M0 -2.5V-11.5M-5 -11.5H5"/>', 14.5),
    "potentiometer": _body('<rect x="-18" y="-7" width="36" height="14"/>', 18)
                     + '<path d="M40 -40V-13"/><path class="fill" d="M40 -8l-4 -7h8z"/>',
    "npn": '<path d="M0 0H30"/><path class="thick" d="M30 -13V13"/><path d="M30 -6L60 -22V-40M30 6L60 22V40"/>'
           '<path class="fill" d="M60 22l-9.5 -0.6l3.4 -6.3z"/><circle cx="46" r="23"/>',
    "pnp": '<path d="M0 0H30"/><path class="thick" d="M30 -13V13"/><path d="M30 -6L60 -22V-40M30 6L60 22V40"/>'
           '<path class="fill" d="M31 7l9.5 0.6l-3.4 6.3z"/><circle cx="46" r="23"/>',
    # enhancement MOSFETs: the gate apart from the channel (three segments: off until driven), the body
    # tied to the source, its arrow into the channel for N, out of it for P
    "nmos": '<path d="M0 0H22M22 -14V14"/><path class="thick" d="M30 -17V-8M30 -4V4M30 8V17"/>'
             '<path d="M30 -12H60V-40M30 12H60V40M30 0H60V12"/><path class="fill" d="M31 0l8 -4.5v9z"/>',
    "pmos": '<path d="M0 0H22M22 -14V14"/><path class="thick" d="M30 -17V-8M30 -4V4M30 8V17"/>'
             '<path d="M30 -12H60V-40M30 12H60V40M30 0H60V12"/><path class="fill" d="M47 0l-8 -4.5v9z"/>',
    "timer555": '<rect x="20" y="20" width="80" height="80"/>'
                '<path d="M0 40H20M0 60H20M0 80H20M100 60H120M40 0V20M80 0V20M40 100V120M80 100V120"/>'
                '<g class="pins"><text x="24" y="43">TRIG</text><text x="24" y="63">THR</text><text x="24" y="83">DIS</text>'
                '<text x="96" y="63" text-anchor="end">OUT</text><text x="40" y="31" text-anchor="middle">VCC</text>'
                '<text x="80" y="31" text-anchor="middle">RST</text><text x="40" y="95" text-anchor="middle">GND</text>'
                '<text x="80" y="95" text-anchor="middle">CV</text></g>'
                '<text class="chip" x="60" y="64" text-anchor="middle">555</text>',
    "arduino": '<rect x="20" y="20" width="320" height="120" rx="6"/>'
               + "".join(f'<path d="M{x * 20} 0V20"/>' for x in (*range(2, 8), *range(9, 17)))
               + "".join(f'<path d="M{x * 20} 140V160"/>' for x in (3, 5, *range(9, 15)))
               + '<g class="pins">'
               + "".join(f'<text x="{(16 - i if i < 8 else 15 - i) * 20}" y="32" text-anchor="middle">{i}</text>'
                         for i in range(14))
               + "".join(f'<text x="{(9 + i) * 20}" y="134" text-anchor="middle">A{i}</text>' for i in range(6))
               + '<text x="60" y="134" text-anchor="middle">5V</text><text x="100" y="134" text-anchor="middle">GND</text>'
               + '</g><text class="chip" x="180" y="86" text-anchor="middle">Arduino Uno</text>',
    "ground": '<path d="M0 0v10M-11 10h22M-7 14h14M-3 18h6"/>',
    "label": "",
    "terminal": '<circle class="open" r="3.5"/>',
}

# IEEE Std 315's own (the rest as in IEC)
IEEE: dict[str, str] = {
    "resistor": _body(ZIGZAG, 18),
    # a cell: the long thin plate is + (the right terminal), the short thick one −
    "voltage_source": _body('<path class="thick" d="M-4 -8V8"/><path d="M4 -15V15"/><path d="M10 -15h6M13 -18v6"/>', 4),
    # the current's arrow inside the circle, the way it pushes the current (left → right)
    "current_source": _body('<circle r="13"/><path d="M-7 0H4"/><path class="fill" d="M9 0l-6 -4.5v9z"/>', 13),
    "potentiometer": _body(ZIGZAG, 18) + '<path d="M40 -40V-15"/><path class="fill" d="M40 -9l-4 -7h8z"/>',
}

STANDARDS = {"iec": {}, "ieee": IEEE}  # a standard: the symbols it draws unlike IEC's
_standard = "iec"


def use(standard: str) -> None:
    """Draw with ``standard``'s symbols from now on ("iec" or "ieee"; anything else: IEC)."""
    global _standard
    _standard = standard if standard in STANDARDS else "iec"


def symbol(kind: str) -> str:
    """A kind's symbol in the standard in use."""
    return STANDARDS[_standard].get(kind, SYMBOLS[kind])


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
.w .when-closed,.closed .when-open{display:none}.closed .when-closed{display:inline}
.w .pins text{font-size:9px;stroke:none;fill:currentColor;opacity:.75}.w text.chip{font-size:13px;font-weight:600;stroke:none;fill:currentColor}
"""


def symbol_library() -> dict:
    """Everything an editor needs to draw elements exactly like the renderer does: IEC's symbols
    (``kinds``), and for each other standard the ones it draws otherwise (``standards``)."""
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
        "standards": {name: dict(own) for name, own in STANDARDS.items()},
    }


def symbol_library_json() -> str:
    return json.dumps(symbol_library(), ensure_ascii=False)
