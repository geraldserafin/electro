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
    "sine_source": _body(
        '<circle r="13"/><path d="M-8 0C-5.5 -9 -2.5 -9 0 0S5.5 9 8 0"/><path d="M20 -13h6M23 -16v6"/>', 13
    ),
    "square_source": _body('<circle r="13"/><path d="M-8 5H-4V-5H4V5H8"/><path d="M20 -13h6M23 -16v6"/>', 13),
    "ammeter": _body('<circle r="13"/>', 13),
    "voltmeter": _body('<circle r="13"/>', 13),
    # controlled sources: a diamond, + inside for a voltage, an arrow for a current; the control side
    # two open terminals (a voltage sensed) or a branch with the current's arrow (a current sensed)
    "vcvs": '<path d="M0 0H14M0 80H14"/><path d="M20 0h8M24 -4v8M20 80h8"/><path d="M80 0V24M80 56V80M80 24L96 40L80 56L64 40Z"/><path d="M76 34h8M80 30v8M76 47h8"/>',
    "vccs": '<path d="M0 0H14M0 80H14"/><path d="M20 0h8M24 -4v8M20 80h8"/><path d="M80 0V24M80 56V80M80 24L96 40L80 56L64 40Z"/><path d="M80 51V38"/><path class="fill" d="M80 31l-4 7h8z"/>',
    "ccvs": '<path d="M0 0V80"/><path class="fill" d="M0 46l-4.5 -8h9z"/><path d="M80 0V24M80 56V80M80 24L96 40L80 56L64 40Z"/><path d="M76 34h8M80 30v8M76 47h8"/>',
    "cccs": '<path d="M0 0V80"/><path class="fill" d="M0 46l-4.5 -8h9z"/><path d="M80 0V24M80 56V80M80 24L96 40L80 56L64 40Z"/><path d="M80 51V38"/><path class="fill" d="M80 31l-4 7h8z"/>',
    # an ideal transformer: two windings facing each other across a core (two lines), dots at p1 and s1
    "transformer": '<path d="M0 0H24V16'
    + "a8 8 0 0 1 0 16" * 3
    + 'V80H0"/><path d="M80 0H56V16'
    + "a8 8 0 0 0 0 16" * 3
    + 'V80H80"/><path d="M37 10V70M43 10V70"/><circle class="fill" cx="28" cy="8" r="2.5"/>'
    '<circle class="fill" cx="52" cy="8" r="2.5"/>',
    "hole": _body('<rect class="dashed" x="-18" y="-10" width="36" height="20"/>', 18),
    "opamp": '<path d="M0 0H20M0 40H20M60 20H80"/><path d="M20 -10L20 50L62 20Z"/>'
    '<path d="M24 0h7M24 40h7M27.5 36.5v7"/>',
    "diode": _body('<path d="M-8 -9L8 0L-8 9Z"/><path d="M8 -9V9"/>', 8),
    "zener": _body('<path d="M-8 -9L8 0L-8 9Z"/><path d="M4 -11L8 -9V9L12 11"/>', 8),  # the bar's ends bent: Z
    "led": _body(
        '<path d="M-8 -9L8 0L-8 9Z"/><path d="M8 -9V9"/>'
        '<path d="M0 -13l7 -8M6 -15l7 -8"/><path class="fill" d="M9 -23.5l-4.5 1.3l3.2 2.8zM15 -25.5l-4.5 1.3l3.2 2.8z"/>',
        8,
    ),
    # a switch or a button drawn open; closed (class "closed" on it, or on the element around it) as it then is
    # the arrows: light falling on it
    "photoresistor": _body(
        '<rect x="-18" y="-7" width="36" height="14"/><path d="M-16 -28L-7 -15M-4 -30L5 -17"/>'
        '<path class="fill" d="M-5 -12l-6 -2l3.5 -3.5zM7 -14l-6 -2l3.5 -3.5z"/>',
        18,
    ),
    # IEC: a line across it with a foot (it follows something non-linearly), −t° beside: NTC
    "thermistor": _body(
        '<rect x="-18" y="-7" width="36" height="14"/><path d="M-24 14H-16L16 -14"/>'
        '<g class="pins"><text x="12" y="-12">−t°</text></g>',
        18,
    ),
    "rgb_led": '<path d="M0 0H18M34 0H60"/><path d="M18 -8L34 0L18 8Z"/><path d="M34 -8V8"/><circle class="on" cx="24" cy="0" r="4" style="stroke:none;fill:#ff3b30;opacity:var(--r,0)"/><path d="M0 40H18M34 40H60"/><path d="M18 32L34 40L18 48Z"/><path d="M34 32V48"/><circle class="on" cx="24" cy="40" r="4" style="stroke:none;fill:#34c759;opacity:var(--g,0)"/><path d="M0 80H18M34 80H60"/><path d="M18 72L34 80L18 88Z"/><path d="M34 72V88"/><circle class="on" cx="24" cy="80" r="4" style="stroke:none;fill:#0a84ff;opacity:var(--b,0)"/><path d="M60 0V80M60 40H80"/><g class="pins"><text x="2" y="-4">R</text><text x="2" y="36">G</text><text x="2" y="76">B</text></g>',
    "seven_segment": '<rect x="-8" y="20" width="96" height="80" rx="3"/><path d="M0 0V20M20 0V20M40 0V20M60 0V20M80 0V20M0 100V120M20 100V120M60 100V120M80 100V120"/><path class="seg" d="M29 32H51"/><path class="seg" d="M54 35V58"/><path class="seg" d="M54 64V87"/><path class="seg" d="M29 90H51"/><path class="seg" d="M26 64V87"/><path class="seg" d="M26 35V58"/><path class="seg" d="M29 61H51"/><circle class="seg" cx="61" cy="90" r="1.5"/><path class="on" d="M29 32H51" style="opacity:var(--a,0)"/><path class="on" d="M54 35V58" style="opacity:var(--b,0)"/><path class="on" d="M54 64V87" style="opacity:var(--c,0)"/><path class="on" d="M29 90H51" style="opacity:var(--d,0)"/><path class="on" d="M26 64V87" style="opacity:var(--e,0)"/><path class="on" d="M26 35V58" style="opacity:var(--f,0)"/><path class="on" d="M29 61H51" style="opacity:var(--g,0)"/><circle class="on" cx="61" cy="90" r="1.5" style="opacity:var(--dp,0)"/><g class="pins"><text x="2" y="14">g</text><text x="22" y="14">f</text><text x="42" y="14">K</text><text x="62" y="14">a</text><text x="82" y="14">b</text><text x="2" y="112">e</text><text x="22" y="112">d</text><text x="62" y="112">c</text><text x="82" y="112">dp</text></g>',
    # a buzzer's dome, + by its a terminal; the waves show while it sounds
    "buzzer": _body(
        '<rect x="-12" y="-6" width="24" height="12"/><path d="M-10 -6A10 10 0 0 1 10 -6"/>'
        '<path d="M-28 -12h6M-25 -15v6"/><path class="waves" style="opacity:var(--sound,0)" d="M-7 -19a9 9 0 0 1 14 0M-11 -25a15 15 0 0 1 22 0"/>',
        12,
    ),
    "passive_buzzer": _body(
        '<rect x="-10" y="-6" width="8" height="12"/><path d="M-2 -6L8 -13V13L-2 6"/><path class="waves" style="opacity:var(--sound,0)" d="M-7 -19a9 9 0 0 1 14 0M-11 -25a15 15 0 0 1 22 0"/>',
        10,
    ),
    "servo": '<path d="M0 0H20M0 20H20M0 40H20"/><rect x="20" y="-14" width="80" height="68" rx="4"/><g class="pins"><text x="24" y="3">S</text><text x="24" y="23">+</text><text x="24" y="43">−</text></g><g class="horn" style="transform-box:fill-box;transform-origin:center;transform:rotate(calc(var(--angle,90) * 1deg - 90deg))"><circle cx="70" cy="20" r="22" style="fill:none;stroke:none"/><path class="thick" d="M70 20V2"/><circle cx="70" cy="20" r="5"/></g>',
    # an HC-SR04: its two transducers; waves while it pings
    "ultrasonic": '<path d="M0 50V80M20 50V80M40 50V80M60 50V80"/><rect x="-32" y="-10" width="124" height="60" rx="3"/><circle cx="0" cy="18" r="17"/><circle cx="0" cy="18" r="10"/><circle cx="60" cy="18" r="17"/><circle cx="60" cy="18" r="10"/><path class="waves" style="opacity:var(--ping,0)" d="M12 -20a26 26 0 0 1 36 0M4 -28a38 38 0 0 1 52 0"/><g class="pins"><text x="0" y="46" text-anchor="middle">Vcc</text><text x="20" y="46" text-anchor="middle">Trig</text><text x="40" y="46" text-anchor="middle">Echo</text><text x="60" y="46" text-anchor="middle">Gnd</text></g>',
    # a 16×2 LCD module: the pins in a row on top, the glass (what it shows is drawn over it while running)
    "lcd1602": '<path d="M0 0V20M20 0V20M40 0V20M60 0V20M80 0V20M100 0V20M120 0V20M140 0V20M160 0V20M180 0V20M200 0V20M220 0V20M240 0V20M260 0V20M280 0V20M300 0V20"/><rect x="-10" y="20" width="320" height="110" rx="4"/><rect x="6" y="44" width="288" height="74" rx="2"/><g class="pins"><text x="0" y="33" text-anchor="middle">VSS</text><text x="20" y="33" text-anchor="middle">VDD</text><text x="40" y="33" text-anchor="middle">V0</text><text x="60" y="33" text-anchor="middle">RS</text><text x="80" y="33" text-anchor="middle">RW</text><text x="100" y="33" text-anchor="middle">E</text><text x="120" y="33" text-anchor="middle">D0</text><text x="140" y="33" text-anchor="middle">D1</text><text x="160" y="33" text-anchor="middle">D2</text><text x="180" y="33" text-anchor="middle">D3</text><text x="200" y="33" text-anchor="middle">D4</text><text x="220" y="33" text-anchor="middle">D5</text><text x="240" y="33" text-anchor="middle">D6</text><text x="260" y="33" text-anchor="middle">D7</text><text x="280" y="33" text-anchor="middle">A</text><text x="300" y="33" text-anchor="middle">K</text></g>',
    # I²C modules: an LCD with its backpack (the glass as the parallel one's, 50 px right, 50 up), a
    # 0.96" OLED (its glass 128 × 64 at 1.5 px a pixel), a clock with its coin cell
    "lcd1602_i2c": '<path d="M0 0H20M0 20H20M0 40H20M0 60H20"/><g class="pins"><text x="24" y="3">GND</text><text x="24" y="23">VCC</text><text x="24" y="43">SDA</text><text x="24" y="63">SCL</text></g><rect x="20" y="-30" width="340" height="110" rx="4"/><rect x="56" y="-6" width="288" height="74" rx="2"/>',
    "ssd1306": '<path d="M0 0V20M20 0V20M40 0V20M60 0V20"/><rect x="-80" y="20" width="220" height="140" rx="4"/><rect x="-66" y="44" width="192" height="96"/><g class="pins"><text x="0" y="33" text-anchor="middle">GND</text><text x="20" y="33" text-anchor="middle">VCC</text><text x="40" y="33" text-anchor="middle">SCL</text><text x="60" y="33" text-anchor="middle">SDA</text></g>',
    # a 2.8" TFT module: its header down the left, the 320×240 glass (1 px a pixel) beside it
    "ili9341": '<path d="M0 0H20M0 20H20M0 40H20M0 60H20M0 80H20M0 100H20M0 120H20M0 140H20M0 160H20"/><rect x="20" y="-50" width="400" height="280" rx="6"/><rect x="66" y="-30" width="320" height="240"/><g class="pins"><text x="26" y="4">VCC</text><text x="26" y="24">GND</text><text x="26" y="44">CS</text><text x="26" y="64">RESET</text><text x="26" y="84">DC</text><text x="26" y="104">MOSI</text><text x="26" y="124">SCK</text><text x="26" y="144">LED</text><text x="26" y="164">MISO</text></g>',
    "ds1307": '<path d="M0 0H20M0 20H20M0 40H20M0 60H20"/><g class="pins"><text x="24" y="3">GND</text><text x="24" y="23">VCC</text><text x="24" y="43">SDA</text><text x="24" y="63">SCL</text></g><rect x="20" y="-30" width="100" height="104" rx="3"/><circle cx="92" cy="30" r="17"/><text class="chip" x="92" y="34" text-anchor="middle">3V</text><g class="pins"><text x="24" y="-16">DS1307</text></g>',
    "switch": _body(
        '<circle class="open" cx="-12" r="2.5"/><circle class="open" cx="12" r="2.5"/>'
        '<path class="when-open" d="M-10 -1.5L11 -12"/><path class="when-closed" d="M-10 -1.5L10 -1.5"/>',
        14.5,
    ),
    "button": _body(
        '<circle class="open" cx="-12" r="2.5"/><circle class="open" cx="12" r="2.5"/>'
        '<path class="when-open" d="M-15 -7H15M0 -7V-16M-5 -16H5"/>'
        '<path class="when-closed" d="M-15 -2.5H15M0 -2.5V-11.5M-5 -11.5H5"/>',
        14.5,
    ),
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
    # a Raspberry Pi Pico standing up, its USB at the top; its LED (GP25) glows while it runs (--led)
    "pico": '<path d="M0 0H20M0 20H20M0 40H20M0 60H20M0 80H20M0 100H20M0 120H20M0 140H20M0 160H20M0 180H20M0 200H20M0 220H20M0 240H20M0 260H20M0 280H20M0 300H20M140 300H160M140 280H160M140 240H160M140 220H160M140 200H160M140 180H160M140 160H160M140 120H160M140 100H160M140 80H160M140 0H160M140 20H160M140 40H160"/><rect x="20" y="-20" width="120" height="340" rx="6"/><rect x="62" y="-30" width="36" height="16" rx="2"/><rect x="52" y="130" width="56" height="40" rx="2"/><text class="chip" x="80" y="154" text-anchor="middle">RP2040</text><circle cx="46" cy="4" r="4"/><circle class="on" cx="46" cy="4" r="4" style="stroke:none;fill:#34c759;opacity:var(--led,0)"/><g class="pins"><text x="24" y="3">GP0</text><text x="24" y="23">GP1</text><text x="24" y="43">GP2</text><text x="24" y="63">GP3</text><text x="24" y="83">GP4</text><text x="24" y="103">GP5</text><text x="24" y="123">GP6</text><text x="24" y="143">GP7</text><text x="24" y="163">GP8</text><text x="24" y="183">GP9</text><text x="24" y="203">GP10</text><text x="24" y="223">GP11</text><text x="24" y="243">GP12</text><text x="24" y="263">GP13</text><text x="24" y="283">GP14</text><text x="24" y="303">GP15</text><text x="136" y="303" text-anchor="end">GP16</text><text x="136" y="283" text-anchor="end">GP17</text><text x="136" y="243" text-anchor="end">GP18</text><text x="136" y="223" text-anchor="end">GP19</text><text x="136" y="203" text-anchor="end">GP20</text><text x="136" y="183" text-anchor="end">GP21</text><text x="136" y="163" text-anchor="end">GP22</text><text x="136" y="123" text-anchor="end">GP26</text><text x="136" y="103" text-anchor="end">GP27</text><text x="136" y="83" text-anchor="end">GP28</text><text x="136" y="3" text-anchor="end">VBUS</text><text x="136" y="23" text-anchor="end">3V3</text><text x="136" y="43" text-anchor="end">GND</text><text x="54" y="7">LED</text></g><text class="chip" x="80" y="260" text-anchor="middle">Pico</text>',
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
    + "".join(
        f'<text x="{(16 - i if i < 8 else 15 - i) * 20}" y="32" text-anchor="middle">{i}</text>' for i in range(14)
    )
    + "".join(f'<text x="{(9 + i) * 20}" y="134" text-anchor="middle">A{i}</text>' for i in range(6))
    + '<text x="60" y="134" text-anchor="middle">5V</text><text x="100" y="134" text-anchor="middle">GND</text>'
    + '</g><text class="chip" x="180" y="86" text-anchor="middle">Arduino Uno</text>',
    # a bulb: a circle with a cross (IEC); it glows with its power (--glow)
    "lamp": _body(
        '<circle class="on" r="13" style="stroke:none;fill:#ffd60a;opacity:var(--glow,0)"/>'
        '<circle r="13"/><path d="M-9.2 -9.2L9.2 9.2M-9.2 9.2L9.2 -9.2"/>',
        13,
    ),
    # a motor: M in a circle (the letter, upright, apart); a mark on its rotor turns with it (--spin, degrees)
    "motor": _body(
        '<circle r="16"/><g style="transform-box:fill-box;transform-origin:center;transform:rotate(calc(var(--spin,0) * 1deg))">'
        '<circle r="16" style="fill:none;stroke:none"/><path class="thick" d="M0 -16V-11"/></g>',
        16,
    ),
    # a relay: its coil (a box) between a and b, the contact beside it — com below, nc straight above
    # it, no to the right; the lever at rest on nc, pulled over to no while the coil holds it (--on)
    "relay": '<path d="M0 0V24M0 56V80"/><rect x="-12" y="24" width="24" height="32"/>'
    '<path d="M80 80V56M80 0V22M120 0V12H104"/><circle class="open" cx="80" cy="24" r="2"/><circle class="open" cx="102" cy="12" r="2"/>'
    '<path d="M80 56L80 27" style="opacity:calc(1 - var(--on,0))"/><path d="M80 56L100 15" style="opacity:var(--on,0)"/>'
    '<path class="dashed" d="M12 40H84"/>'
    '<g class="pins"><text x="68" y="6" text-anchor="end">NC</text><text x="106" y="27">NO</text><text x="86" y="76">COM</text></g>',
    "not_gate": '<path d="M0 0H22M60 0H80"/><rect x="22" y="-16" width="28" height="32"/><circle cx="54" r="4"/>'
    '<text class="chip" x="36" y="5" text-anchor="middle">1</text>',
    "and_gate": '<path d="M0 0H16M0 40H16"/><rect x="16" y="-12" width="36" height="64"/><path d="M52 20H80"/><text class="chip" x="34" y="25" text-anchor="middle">&amp;</text>',
    "nand_gate": '<path d="M0 0H16M0 40H16"/><rect x="16" y="-12" width="36" height="64"/><circle cx="56" cy="20" r="4"/><path d="M60 20H80"/><text class="chip" x="34" y="25" text-anchor="middle">&amp;</text>',
    "or_gate": '<path d="M0 0H16M0 40H16"/><rect x="16" y="-12" width="36" height="64"/><path d="M52 20H80"/><text class="chip" x="34" y="25" text-anchor="middle">≥1</text>',
    "nor_gate": '<path d="M0 0H16M0 40H16"/><rect x="16" y="-12" width="36" height="64"/><circle cx="56" cy="20" r="4"/><path d="M60 20H80"/><text class="chip" x="34" y="25" text-anchor="middle">≥1</text>',
    "xor_gate": '<path d="M0 0H16M0 40H16"/><rect x="16" y="-12" width="36" height="64"/><path d="M52 20H80"/><text class="chip" x="34" y="25" text-anchor="middle">=1</text>',
    "ground": '<path d="M0 0v10M-11 10h22M-7 14h14M-3 18h6"/>',
    "label": "",
    "terminal": '<circle class="open" r="3.5"/>',
    # a component's pin, in its own drawing: a tag pointing at the point (its name above, as a label's)
    "port": '<path d="M0 0L-6 -6V-16H6V-6Z"/>',
    "part": "",  # drawn from its definition: part_symbol()
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

# the distinctive shapes of logic gates
IEEE |= {
    "not_gate": '<path d="M0 0H26M62 0H80"/><path d="M26 -14L54 0L26 14Z"/><circle cx="58" r="4"/>',
    "and_gate": '<path d="M0 0H18M0 40H18"/><path d="M18 -10H38A30 30 0 0 1 38 50H18Z"/><path d="M60 20H80"/>',
    "nand_gate": '<path d="M0 0H18M0 40H18"/><path d="M18 -10H38A30 30 0 0 1 38 50H18Z"/><circle cx="64" cy="20" r="4"/><path d="M68 20H80"/>',
    "or_gate": '<path d="M0 0H24M0 40H24"/><path d="M16 -10Q46 -10 60 20Q46 50 16 50Q28 20 16 -10Z"/><path d="M60 20H80"/>',
    "nor_gate": '<path d="M0 0H24M0 40H24"/><path d="M16 -10Q46 -10 60 20Q46 50 16 50Q28 20 16 -10Z"/><circle cx="64" cy="20" r="4"/><path d="M68 20H80"/>',
    "xor_gate": '<path d="M0 0H24M0 40H24"/><path d="M10 -10Q22 20 10 50"/><path d="M16 -10Q46 -10 60 20Q46 50 16 50Q28 20 16 -10Z"/><path d="M60 20H80"/>',
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


def part_symbol(part) -> str:
    """One's own component (electro_schematic.Part): its box, a lead to each pin, the pins' names
    inside the box and its own name in the middle (the web editor draws it the same: parts.ts)."""
    from html import escape

    w, h = part.size[0] * GRID, part.size[1] * GRID
    leads, names = [], []
    for pin, (px, py) in zip(part.pins, part.offsets()):
        x, y = px * GRID, py * GRID
        name = escape(pin.name)
        if pin.side == "left":
            leads.append(f"M{x} {y}H0")
            names.append(f'<text x="4" y="{y + 3}">{name}</text>')
        elif pin.side == "right":
            leads.append(f"M{x} {y}H{w}")
            names.append(f'<text x="{w - 4}" y="{y + 3}" text-anchor="end">{name}</text>')
        elif pin.side == "top":
            leads.append(f"M{x} {y}V0")
            names.append(f'<text x="{x}" y="11" text-anchor="middle">{name}</text>')
        else:
            leads.append(f"M{x} {y}V{h}")
            names.append(f'<text x="{x}" y="{h - 4}" text-anchor="middle">{name}</text>')
    return (
        f'<rect x="0" y="0" width="{w}" height="{h}" rx="3"/><path d="{"".join(leads)}"/>'
        f'<g class="pins">{"".join(names)}</g>'
        f'<text class="chip" x="{w / 2:g}" y="{h / 2 + 4:g}" text-anchor="middle">{escape(part.name)}</text>'
    )


# Letters stay upright, so they are drawn apart from the (rotating) symbol.
LETTERS = {"ammeter": "A", "voltmeter": "V", "hole": "?", "motor": "M"}

# Symbols that always point down on the page, whatever the element's rotation.
UPRIGHT = {"ground", "label", "terminal", "port"}

STYLE = """
.w{stroke:currentColor;stroke-width:1.6;fill:none;stroke-linecap:round;stroke-linejoin:round}
.w .thick{stroke-width:3}.w .fill{fill:currentColor;stroke:none}.w .dashed{stroke-dasharray:4 3}
.w .open{fill:none}.dot{fill:currentColor}
text{font:13px ui-sans-serif,system-ui,sans-serif;fill:currentColor}.halo{fill:var(--paper,#fff)}
text .sub{font-size:10px}.solved{fill:#2563eb;font-weight:600}.result{fill:#059669}
.node{font-style:italic}.letter{font-weight:600;text-anchor:middle;dominant-baseline:central}
.w .when-closed,.closed .when-open{display:none}.closed .when-closed{display:inline}
.w .seg{stroke-width:4;opacity:.12}.w .on{stroke-width:4;stroke:#ff3b30;fill:#ff3b30}.w .waves{stroke-width:1.4}
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
