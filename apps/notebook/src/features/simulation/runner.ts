// A circuit running in time, with everything the page makes of it: the Arduinos' chips (session.ts),
// the LEDs' glow, the buzzers, servos, LCDs, HC-SR04s, I²C modules and SPI displays (peripherals.ts,
// lcd.ts, i2c.ts, spi.ts), the scope's samples. No React and no DOM: it runs in a worker (sim.worker.ts), off the
// page's thread, and hands over what the board shows as plain data (frame()).

import { i2cParts } from "@/shared/model/i2c";
import type { ElementResult } from "@/shared/model/types";
import { Uno } from "./arduino";
import type { LiveCircuit } from "./engine";
import { si } from "./format";
import { Backpack, type Device, modulesOn, Oled, pixelPath } from "./i2c";
import { type Lcd, lcd, watch as read, type Screen, screen } from "./lcd";
import {
  type Buzzing,
  buzzing,
  heard,
  listen,
  ping,
  type Servoing,
  type Sonar,
  servoing,
  sonar,
  turn,
  watch,
} from "./peripherals";
import { Pico } from "./pico";
import { Session } from "./session";
import { spiDevicesOn } from "./spi";
import type { Ili9341, TftData } from "./tft";

/** A board's program, compiled: an Uno's (Intel HEX), a Pico's (its flash image). */
export type Firmware = { board: "uno"; hex: string } | { board: "pico"; image: Uint8Array };

/** What of an element the runner needs: its kind and text (a position, a reading, an address). */
export interface Part {
  id: string;
  kind: string;
  text: string | null;
}

/** One trace on the scope: a quantity's name and its samples (t, value). */
export interface ScopeTrace {
  name: string;
  t: number[];
  v: number[];
}

/** An OLED's glass: its lit pixels as one path (in pixels), whether it is on, its contrast. */
export interface OledData {
  path: string;
  on: boolean;
  contrast: number;
}

/** What the board shows of the circuit at one moment (and what the page should hear). */
export interface Frame {
  t: number;
  voltages: Record<string, number>; // node → V
  leds: Record<string, number>; // LED id → brightness 0–1
  // what else an element shows, as CSS variables of its symbol: an RGB LED's and a display's glow per
  // channel (r, a, dp, …: 0–1), a servo's angle (degrees), a buzzer sounding (sound: 0 or 1), a ping
  looks: Record<string, Record<string, number>>;
  screens: Record<string, Screen>; // each LCD (parallel or on I²C)
  oleds: Record<string, OledData>;
  tfts: Record<string, TftData>; // each colour TFT, how lit (its pictures come apart: Runner.pictures)
  results: Record<string, ElementResult>; // readings next to the elements
  sounds: { id: string; frequency: number | null; volume: number }[]; // each buzzer, in the circuit's time
  traces: ScopeTrace[]; // the scope's, then the meter's
  serial: string; // what the chips wrote since the last frame
}

const SCOPE_POINTS = 600;
// electro.devices: what glows (each LED's channels: its current's name, "" for I)
const LIGHTS: Record<string, string[]> = {
  LED: [""],
  RGBLED: ["r", "g", "b"],
  SevenSegment: ["a", "b", "c", "d", "e", "f", "g", "dp"],
};
const LCD_DATA = ["d0", "d1", "d2", "d3", "d4", "d5", "d6", "d7"];
const LED_RATED = 0.02; // A: full brightness
const LAMP_RATED = 3; // W: a bulb's full glow, unless its text says otherwise (electro.devices.Lamp)
const SPIN = 0.02; // a motor's drawing turns this much slower than the motor (5700 rpm: about 2 turns a second)

/** The inputs an element sets: [input name, value]. */
function inputsOf(e: Part, pressed: Set<string>): [string, number][] {
  if (e.kind === "switch") return [[`${e.id}_closed`, e.text === "closed" ? 1 : 0]];
  if (e.kind === "button") return [[`${e.id}_closed`, pressed.has(e.id) ? 1 : 0]];
  if (e.kind === "potentiometer") return [[`${e.id}_position`, Number(e.text ?? 0.5)]];
  if (e.kind === "photoresistor") return [[`${e.id}_lux`, Math.max(0.1, Number(e.text ?? 100) || 100)]];
  if (e.kind === "thermistor") return [[`${e.id}_temperature`, Number(e.text ?? 25) || 0]];
  return [];
}

export class Runner {
  readonly session: Session;
  private parts: Part[] = [];
  private pressed = new Set<string>();
  private lights: [string, string, number][]; // each LED's id, channel ("" for a plain one), its current's index in x
  private buzzers: Buzzing[];
  private servos: Servoing[];
  private lcds: Lcd[];
  private sonars: Sonar[];
  private lamps: { id: string; u: number; i: number }[]; // each bulb: its voltage's and current's index in x
  private motors: { id: string; w: number; angle: number }[]; // each motor: its speed's index, how far it turned
  private relays: { id: string; on: number }[];
  private energy = new Map<string, number>(); // each bulb's, since the last frame (its glow: the mean power)
  // the I²C modules, by id: kept across a new sketch (the display keeps what it showed, as a real one does)
  private modules = new Map<string, Device>();
  private tfts = new Map<string, Ili9341>(); // the SPI displays, by id (kept so too)
  // each LED channel's charge since the last frame (id:channel): its glow is the average current, so PWM dims it
  private glow = { since: 0, last: 0, charge: new Map<string, number>() };
  private history = new Map<string, ScopeTrace>();
  private recorded: string[] = []; // the scope's quantities and the meter's
  private shown: { scope: string[]; probe: string[] } = { scope: [], probe: [] };
  private serial = "";
  speed = 1; // the scope's window follows it

  constructor(
    readonly circuit: LiveCircuit,
    parts: Part[],
  ) {
    this.session = new Session(circuit);
    const { kinds, parts: quantities } = circuit.program;
    const having = (kind: string) =>
      Object.entries(kinds)
        .filter(([, k]) => k === kind)
        .map(([id]) => [id, quantities[id]] as const);
    this.lights = Object.entries(kinds).flatMap(([id, kind]) =>
      (LIGHTS[kind] ?? []).flatMap((channel) => {
        const i = quantities[id]?.[channel ? `I_${channel}` : "I"];
        return i === undefined ? [] : [[id, channel, i] as [string, string, number]];
      }),
    );
    this.buzzers = [...having("Buzzer"), ...having("PassiveBuzzer")].flatMap(([id, q]) =>
      q?.U !== undefined ? [buzzing(id, q.U, kinds[id] === "Buzzer")] : [],
    );
    this.servos = having("Servo").flatMap(([id, q]) => (q?.U_sig !== undefined ? [servoing(id, q.U_sig)] : []));
    this.lcds = having("LCD1602").flatMap(([id, q]) =>
      q
        ? [
            lcd(id, {
              power: q.U,
              contrast: q.U_v0,
              backlight: q.I_a,
              rs: q.U_rs,
              rw: q.U_rw,
              e: q.U_e,
              data: LCD_DATA.map((d) => q[`U_${d}`]),
            }),
          ]
        : [],
    );
    this.lamps = having("Lamp").flatMap(([id, q]) =>
      q?.U !== undefined && q.I !== undefined ? [{ id, u: q.U, i: q.I }] : [],
    );
    this.motors = having("Motor").flatMap(([id, q]) => (q?.w !== undefined ? [{ id, w: q.w, angle: 0 }] : []));
    this.relays = having("Relay").flatMap(([id, q]) => (q?.on !== undefined ? [{ id, on: q.on }] : []));
    this.sonars = having("Ultrasonic").flatMap(([id, q]) => (q?.U_trig !== undefined ? [sonar(id, q.U_trig)] : []));
    this.setParts(parts);
  }

  get hasSound() {
    return this.buzzers.length > 0;
  }

  /** The drawing's elements as they are now (a switch flipped, a slider moved) and the buttons held down. */
  setParts(parts: Part[], pressed: string[] = [...this.pressed]) {
    this.parts = parts;
    this.pressed = new Set(pressed);
    for (const e of parts) {
      for (const [name, value] of inputsOf(e, this.pressed)) this.session.sim.setInput(name, value);
      const m = this.modules.get(e.id);
      if (m instanceof Backpack) m.trimmer = i2cParts(e.text).trimmer;
    }
  }

  /** What the scope and the meter show (their samples are kept from now on). */
  watch(scope: string[], probe: string[]) {
    this.shown = { scope, probe };
    this.recorded = [...new Set([...scope, ...probe])];
    this.session.watch(this.recorded);
  }

  /** A board starts running its program (a new one: the chip starts over). */
  attach(id: string, firmware: Firmware) {
    const s = this.session;
    const at = s.boards.findIndex((b) => b.label === id);
    if (at >= 0) s.boards.splice(at, 1);
    const board = s.attach(id, firmware.board === "uno" ? new Uno(firmware.hex) : new Pico(firmware.image));
    board.chip.onSerial = (c) => {
      this.serial = (this.serial + c).slice(-4000);
    };
    board.chip.i2c.devices = modulesOn(
      s,
      board,
      Object.fromEntries(this.parts.map((e) => [e.id, e.text])),
      this.modules,
    );
    spiDevicesOn(s, board, this.tfts);
    this.setParts(this.parts); // (a new LCD takes its trimmer)
  }

  /** How busy the worker is, whether it is behind: the Picos' cores slow down or speed up (Pico.steer). */
  steer(busy: number, behind: boolean) {
    for (const b of this.session.boards) if (b.chip instanceof Pico) b.chip.steer(busy, behind);
  }

  /** Text typed into the serial monitor: to every Arduino's Serial.read(). */
  send(text: string) {
    for (const board of this.session.boards) board.chip.send(text);
  }

  /** On to ``target`` (s), steps of at most ``dtMax``. */
  advanceTo(target: number, dtMax: number) {
    this.session.advanceTo(target, dtMax, () => this.record());
  }

  /** After every step: what glows, sounds, turns and is sampled. */
  private record() {
    const s = this.session,
      x = s.sim.x,
      t = s.sim.t;
    const g = this.glow,
      dt = t - g.last;
    if (dt > 0) {
      for (const [id, channel, i] of this.lights) {
        const key = `${id}:${channel}`;
        g.charge.set(key, (g.charge.get(key) ?? 0) + Math.max(0, x[i]) * dt);
      }
      for (const b of this.buzzers) listen(b, x[b.u], dt);
      for (const l of this.lamps) this.energy.set(l.id, (this.energy.get(l.id) ?? 0) + Math.abs(x[l.u] * x[l.i]) * dt);
      for (const m of this.motors) m.angle = (m.angle + x[m.w] * dt * SPIN * (180 / Math.PI)) % 360;
      g.last = t;
    }
    for (const m of this.servos) watch(m, x[m.u], t);
    for (const d of this.lcds) read(d, x);
    for (const u of this.sonars) {
      // (the distance is looked up only while the trigger is high: a ping is sent as it falls)
      const distance = u.high ? Number(this.parts.find((e) => e.id === u.id)?.text ?? 100) || 100 : 0;
      const echo = ping(u, x[u.trig], t, distance);
      if (!echo) continue;
      const [at, length] = echo,
        input = `${u.id}_echo`;
      s.schedule(at, () => s.sim.setInput(input, 1));
      s.schedule(at + length, () => s.sim.setInput(input, 0));
    }
    // the scope: at most SCOPE_POINTS over its window (two seconds of the page's time, at the speed chosen)
    const window = Math.max(1e-4, this.speed * 2);
    for (const name of this.recorded) {
      let trace = this.history.get(name);
      if (!trace) this.history.set(name, (trace = { name, t: [], v: [] }));
      const last = trace.t[trace.t.length - 1];
      if (last !== undefined && t - last < window / SCOPE_POINTS) continue;
      trace.t.push(t);
      trace.v.push(s.sim.at(name));
      let old = 0;
      while (old < trace.t.length && trace.t[old] < t - window) old++;
      if (old) {
        trace.t.splice(0, old);
        trace.v.splice(0, old);
      }
    }
  }

  /** The colour TFTs' new pictures (Ili9341.picture: each frame whole, or ``anyway`` as it is), by id. */
  pictures(anyway: boolean): Record<string, Uint8ClampedArray> | null {
    let pictures: Record<string, Uint8ClampedArray> | null = null;
    for (const [id, d] of this.tfts) {
      const image = d.picture(anyway);
      if (image) (pictures ??= {})[id] = image;
    }
    return pictures;
  }

  /** What the board shows now; the averages (glow, sound) are over the time since the last frame. */
  frame(): Frame {
    const { sim } = this.session,
      c = this.circuit;
    const voltages: Record<string, number> = {};
    for (const node of Object.keys(c.program.nodes)) voltages[node] = sim.node(node);
    const leds: Record<string, number> = {},
      looks: Record<string, Record<string, number>> = {};
    const span = sim.t - this.glow.since;
    for (const [id, channel, i] of this.lights) {
      const key = `${id}:${channel}`;
      const mean = span > 0 && this.glow.charge.has(key) ? this.glow.charge.get(key)! / span : sim.x[i];
      const bright = Math.min(1, Math.max(0, mean / LED_RATED));
      // a display's segment, an RGB LED's colour: as bright as the eye sees it — about the square root of
      // the current (2 mA of 20 is plainly lit, not a tenth); a plain LED's glow is drawn so (Editor.tsx)
      if (channel) (looks[id] ??= {})[channel] = Math.sqrt(bright);
      else leds[id] = bright;
    }
    const sounds: Frame["sounds"] = [];
    for (const b of this.buzzers) {
      if (span <= 0) continue; // nothing has happened since: it sounds as it did
      const { frequency, volume } = heard(b, span);
      (looks[b.id] ??= {}).sound = frequency === null ? 0 : 1;
      sounds.push({ id: b.id, frequency, volume });
    }
    for (const m of this.servos) (looks[m.id] ??= {}).angle = turn(m, sim.t);
    for (const l of this.lamps) {
      const power =
        span > 0 && this.energy.has(l.id) ? this.energy.get(l.id)! / span : Math.abs(sim.x[l.u] * sim.x[l.i]);
      const rated = Number(this.parts.find((e) => e.id === l.id)?.text?.replace(",", ".")) || LAMP_RATED;
      (looks[l.id] ??= {}).glow = Math.sqrt(Math.min(1, power / rated));
    }
    this.energy.clear();
    for (const m of this.motors) (looks[m.id] ??= {}).spin = m.angle;
    for (const r of this.relays) (looks[r.id] ??= {}).on = sim.x[r.on] > 0.5 ? 1 : 0;
    for (const u of this.sonars) (looks[u.id] ??= {}).ping = sim.t < u.until ? 1 : 0;
    for (const b of this.session.boards) if (b.chip.led !== undefined) (looks[b.label] ??= {}).led = b.chip.led ? 1 : 0;
    const screens: Record<string, Screen> = {};
    for (const d of this.lcds) screens[d.id] = screen(d, sim.x);
    const oleds: Record<string, OledData> = {};
    for (const [id, m] of this.modules) {
      if (m instanceof Backpack) screens[id] = m.screen();
      else if (m instanceof Oled) {
        const { rows, on, contrast } = m.pixels();
        oleds[id] = { path: on ? pixelPath(rows) : "", on, contrast };
      }
    }
    const tfts: Record<string, TftData> = {};
    for (const [id, d] of this.tfts) tfts[id] = d.data();
    const results: Record<string, ElementResult> = {};
    for (const [id, q] of Object.entries(c.program.parts)) {
      const current = q.I ?? q.I_C ?? q.I_D ?? q.I_5V;
      const voltage = q.U ?? q.U_BE ?? q.U_GS;
      const I = current === undefined ? null : sim.x[current];
      results[id] = {
        value: "",
        solved: false,
        U: voltage === undefined ? null : si(Math.abs(sim.x[voltage]), "V"),
        I: I === null ? null : si(Math.abs(I), "A"),
        P: null,
        reversed: I !== null && I < 0,
      };
    }
    // a Pico the emulator cannot keep up with: its cores' clock as they run now, by its label
    for (const b of this.session.boards) {
      if (!(b.chip instanceof Pico) || b.chip.pace > 0.98) continue;
      results[b.label] = {
        value: `${Math.round(b.chip.frequency / 1e6)} MHz`,
        solved: true,
        U: null,
        I: null,
        P: null,
        reversed: false,
      };
    }
    this.glow = { since: sim.t, last: sim.t, charge: new Map() };
    const trace = (name: string) => this.history.get(name) ?? { name, t: [], v: [] };
    const serial = this.serial;
    this.serial = "";
    return {
      t: sim.t,
      voltages,
      leds,
      looks,
      screens,
      oleds,
      tfts,
      results,
      sounds,
      serial,
      traces: [...this.shown.scope, ...this.shown.probe].map(trace),
    };
  }
}
