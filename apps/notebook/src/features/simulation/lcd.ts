// A character LCD's controller, the HD44780 (electro.devices.LCD1602), run in the page: it takes
// what is on its pins when E falls — a byte, or in 4-bit mode half of one, high half first — and
// does what the datasheet says: instructions (RS low) or characters and custom glyphs (RS high).
// Arduino's LiquidCrystal drives it just so; reading back (RW high) is not done here.

const LOGIC = 2.5; // V: an input is high above this
const POWERED = 4; // V: below this across VDD–VSS the controller is off (and forgets)
const LINE = 40; // characters a line holds; 16 are seen

/** Where an LCD's quantities are in x (electro's U_<pin>, the backlight's current I_a). */
export interface LcdPins {
  power: number; contrast: number; backlight: number | undefined;
  rs: number; rw: number; e: number; data: number[]; // d0–d7
}

export interface Lcd {
  id: string;
  pins: LcdPins;
  powered: boolean;
  e: boolean; latch: { rs: boolean; rw: boolean; byte: number }; // what is on the pins while E is high
  eightBit: boolean; half: number | null; // 4-bit: the high half, waiting for the low one
  ddram: Uint8Array; // two lines of LINE characters (addresses 0x00–0x27 and 0x40–0x67)
  cgram: Uint8Array; // eight glyphs of 8 rows, 5 bits each
  address: number; glyphs: boolean; // the address counter, and whether it points into CGRAM
  increment: boolean; follow: boolean; // entry mode: the counter goes up, the display shifts along
  on: boolean; cursor: boolean; blink: boolean; shift: number;
}

export function lcd(id: string, pins: LcdPins): Lcd {
  return {
    id, pins, powered: false, e: false, latch: { rs: false, rw: false, byte: 0 }, eightBit: true, half: null,
    ddram: new Uint8Array(2 * LINE).fill(0x20), cgram: new Uint8Array(64), address: 0, glyphs: false,
    increment: true, follow: false, on: false, cursor: false, blink: false, shift: 0,
  };
}

/** Power-on reset (datasheet: 8-bit, display off, cleared, counting up). */
function reset(d: Lcd) {
  Object.assign(d, lcd(d.id, d.pins), { powered: true });
}

/** The DDRAM address (0x00–0x27, 0x40–0x67) → the index into ``ddram``. */
const cell = (address: number) => (address & 0x40 ? LINE : 0) + (address & 0x3f) % LINE;

function step(d: Lcd, by: number) {
  if (d.glyphs) {
    d.address = (d.address + by) & 0x3f;
    return;
  }
  const line = d.address & 0x40, at = (d.address & 0x3f) + by;
  // past the end of a line the counter goes on to the other one (two-line mode)
  d.address = at >= LINE ? (line ^ 0x40) : at < 0 ? (line ^ 0x40) | (LINE - 1) : line | at;
}

function instruction(d: Lcd, b: number) {
  if (b & 0x80) Object.assign(d, { address: b & 0x7f, glyphs: false });
  else if (b & 0x40) Object.assign(d, { address: b & 0x3f, glyphs: true });
  else if (b & 0x20) { d.eightBit = !!(b & 0x10); d.half = null; }
  else if (b & 0x10) { // shift the display (S/C) or move the cursor, right (R/L) or left
    const by = b & 0x04 ? 1 : -1;
    if (b & 0x08) d.shift = (d.shift - by + LINE) % LINE;
    else step(d, by);
  } else if (b & 0x08) Object.assign(d, { on: !!(b & 0x04), cursor: !!(b & 0x02), blink: !!(b & 0x01) });
  else if (b & 0x04) Object.assign(d, { increment: !!(b & 0x02), follow: !!(b & 0x01) });
  else if (b & 0x02) Object.assign(d, { address: 0, glyphs: false, shift: 0 });
  else if (b & 0x01) { d.ddram.fill(0x20); Object.assign(d, { address: 0, glyphs: false, shift: 0, increment: true }); }
}

function write(d: Lcd, b: number) {
  if (d.glyphs) d.cgram[d.address & 0x3f] = b & 0x1f;
  else d.ddram[cell(d.address)] = b;
  step(d, d.increment ? 1 : -1);
  if (d.follow && !d.glyphs) d.shift = (d.shift + (d.increment ? 1 : -1) + LINE) % LINE;
}

function take(d: Lcd, rs: boolean, b: number) {
  if (rs) write(d, b);
  else instruction(d, b);
}

/** The pins at time ``t`` (``x``: the circuit's unknowns); after every step. */
export function watch(d: Lcd, x: ArrayLike<number>) {
  const powered = x[d.pins.power] > POWERED;
  if (powered !== d.powered) {
    if (powered) reset(d);
    else d.powered = false;
  }
  if (!powered) return;
  const e = x[d.pins.e] > LOGIC;
  if (e) { // what it will take when E falls (the pins settle while it is high)
    let byte = 0;
    d.pins.data.forEach((i, bit) => { if (x[i] > LOGIC) byte |= 1 << bit; });
    d.latch = { rs: x[d.pins.rs] > LOGIC, rw: x[d.pins.rw] > LOGIC, byte };
  } else if (d.e && !d.latch.rw) {
    const { rs, byte } = d.latch;
    if (d.eightBit) take(d, rs, byte);
    else if (d.half === null) d.half = byte & 0xf0;
    else {
      take(d, rs, d.half | (byte >> 4));
      d.half = null;
    }
  }
  d.e = e;
}

/** What it shows now: two lines of 16 character codes, the glyphs, the cursor, how dark and lit. */
export interface Screen {
  lines: number[][]; // character codes (0–15: a glyph from CGRAM)
  text: string[][]; // the same as text (glyph())
  cgram: number[];
  cursor: [number, number] | null; // column, line — where the underline or the blinking block is
  underline: boolean;
  blink: boolean;
  contrast: number; // 0 (unreadable) – 1
  backlight: number; // 0–1
}

export function screen(d: Lcd, x: ArrayLike<number>): Screen {
  const volts = x[d.pins.power];
  const contrast = d.powered && d.on ? Math.max(0, Math.min(1, (volts - x[d.pins.contrast] - 2.5) / 1.5)) : 0;
  const lines = [0, 1].map((line) => Array.from({ length: 16 }, (_, col) => d.ddram[line * LINE + (col + d.shift) % LINE]));
  let cursor: [number, number] | null = null;
  if ((d.cursor || d.blink) && !d.glyphs) {
    const col = ((d.address & 0x3f) - d.shift + LINE) % LINE;
    if (col < 16) cursor = [col, d.address & 0x40 ? 1 : 0];
  }
  const lit = d.pins.backlight === undefined ? 0 : Math.max(0, Math.min(1, x[d.pins.backlight] / 0.02));
  return { lines, text: lines.map((line) => line.map(glyph)), cgram: [...d.cgram], cursor, underline: d.cursor, blink: d.blink,
    contrast, backlight: lit };
}

/** A character of the A00 ROM (the usual one) as text: ASCII mostly, ¥ and arrows, katakana, a few Greek letters. */
export function glyph(code: number): string {
  if (code === 0x5c) return "¥";
  if (code === 0x7e) return "→";
  if (code === 0x7f) return "←";
  if (code >= 0x20 && code < 0x7e) return String.fromCharCode(code);
  if (code === 0xdf) return "°";
  if (code >= 0xa1 && code < 0xdf) return String.fromCharCode(0xff61 + code - 0xa1); // half-width katakana
  const greek: Record<number, string> = { 0xe0: "α", 0xe2: "β", 0xe3: "ε", 0xe4: "µ", 0xe5: "σ", 0xe6: "ρ", 0xf2: "θ",
    0xf3: "∞", 0xf4: "Ω", 0xf6: "Σ", 0xf7: "π", 0xfd: "÷", 0xff: "█" };
  return greek[code] ?? " ";
}
