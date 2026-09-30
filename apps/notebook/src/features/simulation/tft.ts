// A 2.8" 320×240 colour TFT's controller, an ILI9341, as the bytes of SPI come to it (spi.ts): a
// command when D/C is low, its parameters and pixels when high; the frame memory — 240 columns of
// 320 rows, portrait as the glass is made — written in a window (CASET, PASET) from RAMWR on, the
// memory access control (MADCTL) deciding how the window's columns and pages lie on it (MV: exchanged,
// Adafruit_ILI9341's landscape; MX, MY: mirrored) and in which order a pixel's colours are (BGR).
// The glass is drawn landscape: 320 wide, 240 high.

export const WIDTH = 320,
  HEIGHT = 240; // the glass, landscape
const COLUMNS = 240,
  ROWS = 320; // the frame memory

/** What the display is wired to, asked as each byte comes (spi.ts). */
export interface Wiring {
  powered(): boolean;
  selected(): boolean; // CS low
  reset(): boolean; // RESET held low
  data(): boolean; // D/C high: a parameter or pixels
  backlight(): number; // 0–1, from its LED pin
}

/** How the glass is lit (its picture comes apart: picture()). */
export interface TftData {
  shown: boolean; // the controller drives the glass (powered, awake, display on); else it is blank
  backlight: number; // 0–1
}

export class Ili9341 {
  private ram = new Uint16Array(COLUMNS * ROWS).fill(0); // 5-6-5 as written
  private wiring: Wiring | null = null;
  private command = 0;
  private params: number[] = [];
  private madctl = 0;
  private bits = 16; // per pixel (COLMOD: 16 or 18)
  private sleeping = true;
  private on = false;
  private inverted = false;
  private columns = [0, COLUMNS - 1];
  private pages = [0, ROWS - 1];
  private column = 0;
  private page = 0;
  private pixel = 0; // the bytes of a pixel so far, and how many (a pixel comes byte by byte: no array for it)
  private have = 0;
  private wasReset = false;
  private dirty = true; // changed since the picture was last taken
  // a frame written whole: a large window written to its end — the frame memory then (the picture taken
  // from it: not half of one frame, half of the next) — since the picture was last taken; changed since
  private frame = new Uint16Array(COLUMNS * ROWS);
  private finished = false;
  private since = true;

  constructor(readonly id: string) {}

  wire(wiring: Wiring) {
    this.wiring = wiring;
  }

  transmit(byte: number) {
    if (!this.listening()) return;
    if (!this.wiring!.data()) this.begin(byte);
    else if (this.command === 0x2c || this.command === 0x3c) this.write(byte);
    else this.parameter(byte);
  }

  /** Bytes one after another (the pins as they are: nothing runs between them), as many transmit()s. */
  transmitMany(memory: DataView, offset: number, count: number, size: number, mask: number) {
    if (!this.listening()) return;
    const byte = (i: number) =>
      (size === 2 ? memory.getUint16(offset + 2 * i, true) : memory.getUint8(offset + i)) & mask;
    if (!this.wiring!.data()) for (let i = 0; i < count; i++) this.begin(byte(i));
    else if (this.command === 0x2c || this.command === 0x3c) {
      if (size === 1) for (let i = 0; i < count; i++) this.write(memory.getUint8(offset + i) & mask);
      else for (let i = 0; i < count; i++) this.write(byte(i));
    } else for (let i = 0; i < count; i++) this.parameter(byte(i));
  }

  // powered, not held in reset (just held: reset), selected
  private listening(): boolean {
    const w = this.wiring;
    if (!w?.powered()) return false;
    const held = w.reset();
    if (held !== this.wasReset) {
      this.wasReset = held;
      if (held) this.hardwareReset();
    }
    return !held && w.selected();
  }

  private hardwareReset() {
    this.sleeping = true;
    this.on = false;
    this.inverted = false;
    this.madctl = 0;
    this.bits = 16;
    this.columns = [0, COLUMNS - 1];
    this.pages = [0, ROWS - 1];
    this.command = 0;
    this.dirty = this.since = true;
  }

  private begin(command: number) {
    this.command = command;
    this.params = [];
    this.have = 0;
    switch (command) {
      case 0x01:
        this.hardwareReset();
        break; // SWRESET
      case 0x10:
        this.sleeping = true;
        this.dirty = this.since = true;
        break; // SLPIN
      case 0x11:
        this.sleeping = false;
        this.dirty = this.since = true;
        break; // SLPOUT
      case 0x20:
        this.inverted = false;
        this.dirty = this.since = true;
        break; // INVOFF
      case 0x21:
        this.inverted = true;
        this.dirty = this.since = true;
        break; // INVON
      case 0x28:
        this.on = false;
        this.dirty = this.since = true;
        break; // DISPOFF
      case 0x29:
        this.on = true;
        this.dirty = this.since = true;
        break; // DISPON
      case 0x2c:
        this.column = this.columns[0];
        this.page = this.pages[0];
        break; // RAMWR (RAMWRC 0x3c goes on)
    }
  }

  private parameter(byte: number) {
    const p = this.params;
    p.push(byte);
    if (this.command === 0x2a && p.length === 4)
      this.columns = [(p[0] << 8) | p[1], (p[2] << 8) | p[3]]; // CASET
    else if (this.command === 0x2b && p.length === 4)
      this.pages = [(p[0] << 8) | p[1], (p[2] << 8) | p[3]]; // PASET
    else if (this.command === 0x36 && p.length === 1) {
      this.madctl = byte;
      this.dirty = this.since = true;
    } // MADCTL
    else if (this.command === 0x3a && p.length === 1) this.bits = (byte & 0x07) === 0x06 ? 18 : 16; // COLMOD
  }

  private write(byte: number) {
    this.pixel = (this.pixel << 8) | byte;
    if (++this.have < (this.bits === 16 ? 2 : 3)) return;
    const px = this.pixel;
    const value =
      this.bits === 16 ? px & 0xffff : (((px >> 19) & 31) << 11) | (((px >> 10) & 63) << 5) | ((px >> 3) & 31); // 6-6-6: the top bits of each byte
    this.pixel = 0;
    this.have = 0;
    const exchanged = (this.madctl & 0x20) !== 0;
    let col = exchanged ? this.page : this.column,
      row = exchanged ? this.column : this.page;
    if (this.madctl & 0x40) col = COLUMNS - 1 - col; // MX
    if (this.madctl & 0x80) row = ROWS - 1 - row; // MY
    const i = row * COLUMNS + col;
    if (col >= 0 && col < COLUMNS && row >= 0 && row < ROWS && this.ram[i] !== value) {
      this.ram[i] = value;
      this.dirty = this.since = true; // (the same again: nothing to send — a still screen costs nothing)
    }
    if (++this.column > this.columns[1]) {
      this.column = this.columns[0];
      if (++this.page > this.pages[1]) {
        this.page = this.pages[0];
        if (this.since && this.large()) {
          this.frame.set(this.ram);
          this.finished = true;
          this.since = false;
        }
      }
    }
  }

  // a window of half the frame memory or more: a program writing whole frames (Doom: 320 × 200)
  private large(): boolean {
    const [c0, c1] = this.columns,
      [p0, p1] = this.pages;
    return (c1 - c0 + 1) * (p1 - p0 + 1) >= (COLUMNS * ROWS) / 2;
  }

  /** How the glass is lit now. */
  data(): TftData {
    const w = this.wiring;
    const powered = !!w?.powered();
    return { shown: powered && !this.sleeping && this.on, backlight: powered ? w!.backlight() : 0 };
  }

  /**
   * The picture (RGBA, WIDTH × HEIGHT: a new array, the caller's), if something changed since it was last
   * taken: the last frame written whole, if one was since; else, ``anyway``, the frame memory as it is —
   * but for a frame being written whole (a large window: its picture when it is); else null.
   */
  picture(anyway: boolean): Uint8ClampedArray | null {
    if (!this.dirty || !this.data().shown || !(this.finished || (anyway && !this.large()))) return null;
    const memory = this.finished ? this.frame : this.ram;
    this.dirty = this.finished && this.since; // (changed after that frame: more to take)
    this.finished = false;
    if (memory === this.ram) this.since = false;
    // the frame memory's row r, column c lies at (r, c) on the landscape glass; the colours as the panel
    // takes them: BGR set, the high 5 bits are red (Adafruit_ILI9341); clear, they are blue
    const bgr = (this.madctl & 0x08) !== 0,
      invert = this.inverted ? 0xffff : 0,
      out = new Uint8ClampedArray(WIDTH * HEIGHT * 4);
    for (let r = 0; r < ROWS; r++) {
      for (let c = 0; c < COLUMNS; c++) {
        const v = memory[r * COLUMNS + c] ^ invert,
          o = (c * WIDTH + r) * 4;
        const hi = (v >> 11) & 31,
          g = (v >> 5) & 63,
          lo = v & 31;
        out[o] = ((bgr ? hi : lo) * 527 + 23) >> 6;
        out[o + 1] = (g * 259 + 33) >> 6;
        out[o + 2] = ((bgr ? lo : hi) * 527 + 23) >> 6;
        out[o + 3] = 255;
      }
    }
    return out;
  }
}
