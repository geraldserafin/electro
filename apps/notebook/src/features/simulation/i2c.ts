// I²C between an emulated Uno and the devices on its A4 (SDA) and A5 (SCL): avr8js's TWI hands over
// whole transactions — a start, an address, bytes, a stop — not the lines' levels, so the bus is
// here, in the page, and the devices on it are emulated as the chips they are: a PCF8574 behind a
// character LCD, an SSD1306 OLED, a DS1307 clock.
import type { TWIEventHandler } from "avr8js";
import { i2cParts, TRIMMER } from "@/shared/model/i2c";
import { type Lcd, lcd, type Screen, screen, watch } from "./lcd";
import type { Board, Session } from "./session";

/** A chip on the bus: it answers to ``address`` while ``powered()``. */
export interface Device {
  address: number;
  powered: () => boolean;
  begin(write: boolean): void; // addressed (a start, or a repeated one)
  write(byte: number): boolean; // a byte from the master: acknowledged?
  read(): number; // a byte to the master
  end(): void; // the stop
}

/** The chip's side of a transaction: avr8js's TWI and rp2040js's I²C both answer so. */
export interface Controller {
  completeStart(): void;
  completeStop(): void;
  completeConnect(ack: boolean): void;
  completeWrite(ack: boolean): void;
  completeRead(value: number): void;
}

export class Bus implements TWIEventHandler {
  devices: Device[] = [];
  private current: Device | null = null;

  constructor(private twi: Controller) {}

  start() {
    this.current?.end();
    this.current = null;
    this.twi.completeStart();
  }

  stop() {
    this.current?.end();
    this.current = null;
    this.twi.completeStop();
  }

  connectToSlave(address: number, write: boolean) {
    this.current = this.devices.find((d) => d.address === address && d.powered()) ?? null;
    this.current?.begin(write);
    this.twi.completeConnect(this.current !== null);
  }

  writeByte(byte: number) {
    this.twi.completeWrite(this.current?.write(byte) ?? false);
  }

  readByte() {
    this.twi.completeRead(this.current?.read() ?? 0xff); // nobody drives SDA: the pull-up reads 1s
  }
}

// ------------------------------------------------------------------ PCF8574 + HD44780

/**
 * An LCD's I²C backpack: a PCF8574 whose eight outputs are the LCD's pins — P0 RS, P1 RW, P2 E,
 * P3 the backlight, P4–P7 D4–D7 — as LiquidCrystal_I2C has it. Every byte written is the pins, so
 * the controller (lcd.ts) sees each of them as a moment of its pins.
 */
export class Backpack implements Device {
  readonly lcd: Lcd;
  /** The contrast trimmer on its back, 0–1: it sets V0 (0.7: VDD − V0 ≈ 4.25 V, as it best shows). */
  trimmer = TRIMMER;
  private pins = 0xff; // quasi-bidirectional: high after reset
  private x = new Float64Array(14); // lcd.ts's view: the supply, the contrast, RS, RW, E, D0–D7, the backlight's current

  constructor(
    readonly id: string,
    readonly address: number,
    readonly powered: () => boolean,
  ) {
    this.lcd = lcd(id, { power: 0, contrast: 1, backlight: 13, rs: 2, rw: 3, e: 4, data: [5, 6, 7, 8, 9, 10, 11, 12] });
  }

  begin() {}
  end() {}

  write(byte: number) {
    this.pins = byte;
    this.sample();
    return true;
  }

  read() {
    return this.pins;
  }

  /** The LCD's pins as the backpack drives them (and without power, nothing). */
  sample() {
    const x = this.x,
      p = this.pins,
      on = this.powered();
    x[0] = on ? 5 : 0;
    x[1] = 2.5 * (1 - this.trimmer); // V0: VDD − V0 from 2.5 V (nothing shown) to 5 V (boxes)
    x[2] = p & 0x01 ? 5 : 0;
    x[3] = p & 0x02 ? 5 : 0;
    x[4] = p & 0x04 ? 5 : 0;
    x[13] = on && p & 0x08 ? 0.02 : 0;
    for (let bit = 4; bit < 8; bit++) x[5 + bit] = p & (1 << bit) ? 5 : 0;
    watch(this.lcd, x);
  }

  screen(): Screen {
    this.sample(); // switched off (or on) since the last byte: the controller knows
    return screen(this.lcd, this.x);
  }
}

// ------------------------------------------------------------------ SSD1306

// commands that take parameters: how many bytes follow
const PARAMETERS: Record<number, number> = {
  129: 1,
  32: 1,
  33: 2,
  34: 2,
  168: 1,
  211: 1,
  213: 1,
  217: 1,
  218: 1,
  219: 1,
  141: 1,
  38: 6,
  39: 6,
  41: 5,
  42: 5,
  163: 2,
};

/** What an OLED shows: 64 rows of 128 pixels (lit or not), and whether it is on. */
export interface Pixels {
  rows: Uint8Array[]; // 64 × 128, 1: lit
  on: boolean;
  contrast: number; // 0–1
}

/**
 * A 128×64 OLED's controller: a control byte (0x00: commands follow, 0x40: data; bit 7: only one
 * byte, then another control byte), commands with their parameters, data into GDDRAM — 8 pages
 * of 128 columns, a byte a column, bit 0 on top — in the addressing mode set (Adafruit_SSD1306:
 * horizontal, within the column and page range it sets).
 */
export class Oled implements Device {
  ram = new Uint8Array(8 * 128);
  on = false;
  invert = false;
  entire = false;
  contrast = 0x7f;
  flipX = false;
  flipY = false;
  startLine = 0;
  mode = 2; // page addressing after reset
  column = 0;
  page = 0;
  columns = [0, 127];
  pages = [0, 7];
  private control: number | null = null; // the control byte in force; null: the next byte is one
  private command: number[] = []; // a command waiting for its parameters

  constructor(
    readonly id: string,
    readonly address: number,
    readonly powered: () => boolean,
  ) {}

  begin() {
    this.control = null;
  }

  end() {}

  read() {
    return 0; // status: nothing busy
  }

  write(byte: number) {
    if (this.control === null) {
      this.control = byte;
      return true;
    }
    if (this.control & 0x40) this.data(byte);
    else this.take(byte);
    if (this.control & 0x80) this.control = null; // Co: one byte, then a control byte again
    return true;
  }

  private take(byte: number) {
    const c = this.command;
    c.push(byte);
    if (c.length <= (PARAMETERS[c[0]] ?? 0)) return;
    this.command = [];
    const [op, a, b] = c;
    if (op === 0xae || op === 0xaf) this.on = op === 0xaf;
    else if (op === 0x81) this.contrast = a;
    else if (op === 0xa4 || op === 0xa5) this.entire = op === 0xa5;
    else if (op === 0xa6 || op === 0xa7) this.invert = op === 0xa7;
    else if (op === 0x20) this.mode = a & 3;
    else if (op === 0x21) Object.assign(this, { columns: [a & 127, b & 127], column: a & 127 });
    else if (op === 0x22) Object.assign(this, { pages: [a & 7, b & 7], page: a & 7 });
    else if (op >= 0xb0 && op <= 0xb7) this.page = op & 7;
    else if (op <= 0x0f) this.column = (this.column & 0xf0) | op;
    else if (op <= 0x1f) this.column = (this.column & 0x0f) | ((op & 0x0f) << 4);
    else if (op >= 0x40 && op <= 0x7f) this.startLine = op & 63;
    else if (op === 0xa0 || op === 0xa1) this.flipX = op === 0xa1;
    else if (op === 0xc0 || op === 0xc8) this.flipY = op === 0xc8;
  }

  private data(byte: number) {
    this.ram[this.page * 128 + this.column] = byte;
    const [c0, c1] = this.columns,
      [p0, p1] = this.pages;
    if (this.mode === 0) {
      // horizontal: along the page, then the next one
      if (this.column < c1) this.column++;
      else {
        this.column = c0;
        this.page = this.page < p1 ? this.page + 1 : p0;
      }
    } else if (this.mode === 1) {
      // vertical: down the column, then the next one
      if (this.page < p1) this.page++;
      else {
        this.page = p0;
        this.column = this.column < c1 ? this.column + 1 : c0;
      }
    } else this.column = Math.min(127, this.column + 1); // page mode: along the page, and stay at its end
  }

  /** The glass, as seen: the module's glass is wired mirrored, so A1 and C8 (Adafruit's) show it upright. */
  pixels(): Pixels {
    const rows = Array.from({ length: 64 }, () => new Uint8Array(128));
    for (let y = 0; y < 64; y++) {
      const row = ((this.flipY ? y : 63 - y) + this.startLine) & 63;
      for (let x = 0; x < 128; x++) {
        const col = this.flipX ? x : 127 - x;
        const lit = this.entire || ((this.ram[(row >> 3) * 128 + col] >> (row & 7)) & 1) === 1;
        rows[y][x] = lit !== this.invert ? 1 : 0;
      }
    }
    return { rows, on: this.on && this.powered(), contrast: 0.35 + (0.65 * this.contrast) / 255 };
  }
}

/** Rows of pixels (1: lit) → the path: each run of lit pixels in a row one rectangle. */
export function pixelPath(rows: ArrayLike<number>[]): string {
  let d = "";
  for (let y = 0; y < rows.length; y++) {
    const row = rows[y];
    for (let x = 0; x < row.length; x++) {
      if (!row[x]) continue;
      const from = x;
      while (x + 1 < row.length && row[x + 1]) x++;
      d += `M${from} ${y}h${x - from + 1}v1h${from - x - 1}z`;
    }
  }
  return d;
}

// ------------------------------------------------------------------ DS1307

const bcd = (n: number) => (((n / 10) | 0) << 4) | (n % 10);
const unbcd = (b: number) => (b >> 4) * 10 + (b & 15);

/**
 * A real-time clock: registers 0–6 the time in BCD (seconds, minutes, hours, weekday, date, month,
 * year), 7 the control byte, 8–63 RAM. It runs with the circuit's time, from the moment the
 * simulation started at the page's wall-clock time; setting it (RTClib's adjust()) moves it.
 */
export class Clock implements Device {
  private pointer = 0;
  private first = false; // the next byte written sets the pointer
  private ram = new Uint8Array(64);
  private offset = 0; // ms the clock is ahead of the wall clock at the start
  private written = false; // the time was set in this transaction: taken at its stop

  constructor(
    readonly id: string,
    readonly address: number,
    readonly powered: () => boolean,
    private now: () => number,
    private start = Date.now(),
  ) {} // now(): the circuit's time, s

  /** Its time now, as a Date read in UTC (the clock does not know time zones: the page's local time is put in as is). */
  private time() {
    const local = this.start - new Date(this.start).getTimezoneOffset() * 60000;
    return new Date(local + this.offset + this.now() * 1000);
  }

  begin(write: boolean) {
    this.first = write;
    if (!write) this.latch();
  }

  /** The time into registers 0–6, for a read. */
  private latch() {
    const t = this.time();
    this.ram.set(
      [
        bcd(t.getUTCSeconds()),
        bcd(t.getUTCMinutes()),
        bcd(t.getUTCHours()),
        t.getUTCDay() + 1,
        bcd(t.getUTCDate()),
        bcd(t.getUTCMonth() + 1),
        bcd(t.getUTCFullYear() % 100),
      ],
      0,
    );
  }

  write(byte: number) {
    if (this.first) {
      this.pointer = byte & 63;
      this.first = false;
      this.latch();
      return true;
    }
    if (this.pointer < 7) this.written = true;
    this.ram[this.pointer] = byte;
    this.pointer = (this.pointer + 1) & 63;
    return true;
  }

  read() {
    const byte = this.ram[this.pointer];
    this.pointer = (this.pointer + 1) & 63;
    return byte;
  }

  end() {
    if (!this.written) return;
    this.written = false;
    const r = this.ram;
    const hours = r[2] & 0x40 ? (unbcd(r[2] & 0x1f) % 12) + (r[2] & 0x20 ? 12 : 0) : unbcd(r[2] & 0x3f); // 12- or 24-hour
    const set = Date.UTC(
      2000 + unbcd(r[6]),
      unbcd(r[5] & 0x1f) - 1,
      unbcd(r[4] & 0x3f),
      hours,
      unbcd(r[1] & 0x7f),
      unbcd(r[0] & 0x7f),
    );
    this.offset = 0;
    this.offset = set - this.time().getTime();
  }
}

// ------------------------------------------------------------------ on a board

const MODULES: Record<string, number> = { LCD1602I2C: 0x27, SSD1306: 0x3c, DS1307: 0x68 }; // electro's kinds, the address they come set to

/**
 * The I²C modules on ``board``'s bus: those whose SDA and SCL are wired to its chip's (an Uno's A4 and A5,
 * a Pico's GP4 and GP5); each
 * answers while it has power. ``addresses``: each element's address as set (its text); ``kept``:
 * the modules made so far, by id — reused, so a display keeps what it showed across a new sketch.
 */
export function modulesOn(
  s: Session,
  board: Board,
  addresses: Record<string, string | null>,
  kept: Map<string, Device>,
): Device[] {
  const { pins, program } = s.circuit;
  const at = (id: string, i: number) => pins[id]?.[i] ?? null;
  const sda = board.pins[board.chip.sda],
    scl = board.pins[board.chip.scl];
  if (!sda || !scl) return [];
  const devices: Device[] = [];
  for (const [id, kind] of Object.entries(program.kinds)) {
    if (!MODULES[kind]) continue;
    const [gnd, vcc, a, b] = [0, 1, 2, 3].map((i) => at(id, i));
    const [dsa, dcl] = kind === "SSD1306" ? [b, a] : [a, b]; // an OLED's pins: SCL before SDA
    if (dsa !== sda || dcl !== scl) continue;
    const powered = () => s.sim.node(vcc ?? "") - s.sim.node(gnd ?? "") > 3;
    const address = Number(i2cParts(addresses[id]).address) || MODULES[kind];
    let m = kept.get(id);
    if (!m || m.address !== address) {
      m =
        kind === "LCD1602I2C"
          ? new Backpack(id, address, powered)
          : kind === "SSD1306"
            ? new Oled(id, address, powered)
            : new Clock(id, address, powered, () => s.clock(board));
      kept.set(id, m);
    }
    devices.push(m);
  }
  return devices;
}
