"""Writes src/features/schematic/lcdFont.ts: an HD44780's character ROM (A00, the usual one) as 8 rows
of 5 dots for each of the 256 codes, for drawing an LCD dot by dot.

From Adafruit GFX's classic 5×7 font (glcdfont.c, BSD licence — see the file written): ASCII, and a
few Greek letters and symbols where A00 has them too; the codes where A00 differs from that font
(¥, →, ←, °, █) drawn here. A00's katakana are not in it: those codes stay blank. Run from the repo
root with arduino-cli's user libraries installed (Adafruit GFX Library: devenv installs it).
"""

import re
import subprocess
from pathlib import Path

user = subprocess.run(
    ["arduino-cli", "config", "get", "directories.user"], capture_output=True, text=True, check=True
).stdout.strip()
source = (Path(user) / "libraries/Adafruit_GFX_Library/glcdfont.c").read_text()
table = [int(h, 16) for h in re.findall(r"0x([0-9A-Fa-f]{2})", source.split("font[] PROGMEM = {")[1].split("};")[0])]
assert len(table) == 256 * 5


def glyph(code: int) -> list[int]:
    """The font's glyph (columns, bit 0 on top) as 8 rows of 5 dots (bit 4 on the left, as CGRAM has them)."""
    cols = table[code * 5 : code * 5 + 5]
    return [sum(1 << (4 - c) for c in range(5) if cols[c] >> r & 1) for r in range(8)]


rows = lambda *pattern: [int(p, 2) for p in pattern] + [0] * (8 - len(pattern))
rom = [[0] * 8 for _ in range(256)]
for code in range(0x20, 0x7E):
    rom[code] = glyph(code)
rom[0x5C] = rows("10001", "01010", "11111", "00100", "11111", "00100", "00100")  # ¥
rom[0x7E] = rows("00000", "00100", "00010", "11111", "00010", "00100")  # →
rom[0x7F] = rows("00000", "00100", "01000", "11111", "01000", "00100")  # ←
rom[0xDF] = rows("11100", "10100", "11100")  # ° (lcd.print((char)223))
rom[0xFF] = [0b11111] * 8  # █
# A00's Greek letters and symbols, from the font's CP437 ones that look alike
for a00, cp437 in {
    0xE0: 0xE0,
    0xE2: 0xE1,
    0xE3: 0xEE,
    0xE4: 0xE6,
    0xE5: 0xE5,
    0xF2: 0xE9,
    0xF3: 0xEC,
    0xF4: 0xEA,
    0xF6: 0xE4,
    0xF7: 0xE3,
    0xFD: 0xF6,
}.items():
    rom[a00] = glyph(cp437)

hex_rows = "".join(f"{r:02x}" for g in rom for r in g)
out = Path(__file__).parent.parent / "src/features/schematic/lcdFont.ts"
out.write_text(f"""// An HD44780's character ROM (A00): 8 rows of 5 dots (bit 4 on the left) for each of the 256 codes.
// Written by scripts/make_lcd_font.py from Adafruit GFX's classic font (glcdfont.c):
//
// Software License Agreement (BSD License). Copyright (c) 2012 Adafruit Industries. All rights reserved.
// Redistribution and use in source and binary forms, with or without modification, are permitted provided
// that the following conditions are met: redistributions of source code must retain the above copyright
// notice, this list of conditions and the following disclaimer; redistributions in binary form must
// reproduce the above copyright notice, this list of conditions and the following disclaimer in the
// documentation and/or other materials provided with the distribution. Neither the name of the copyright
// holders nor the names of its contributors may be used to endorse or promote products derived from this
// software without specific prior written permission. THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS
// AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
// WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
// COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
// CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF
// USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
// CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
// OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

const HEX = "{hex_rows}";

/** ROM[code * 8 + row]: the row's 5 dots. */
export const ROM = Uint8Array.from(HEX.match(/../g)!, (h) => parseInt(h, 16));
""")
print(out)
