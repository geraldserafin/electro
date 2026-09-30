// What the session needs of a board's chip, whichever it is (arduino.ts: an Uno's ATmega328P,
// pico.ts: a Pico's RP2040): it runs its program, says when its pins change, reads what the
// circuit puts on them, and has a serial port and an I²C bus.
import type { Bus } from "./i2c";

/** What a chip makes of a pin: electro.devices' MODES (a source with a resistance, per board). */
export type Mode = "input" | "pullup" | "pulldown" | "low" | "high";

/** A pin that changed: when (s since the chip was reset), which (as electro names it: D13, GP15), to what. */
export interface PinChange {
  time: number;
  pin: string;
  mode: Mode;
}

export interface Chip {
  readonly pins: readonly string[]; // the board's I/O pins, in its terminals' order (its supplies and GND follow)
  readonly modes: Record<Mode, [number, number]>; // conductance to the pin's source (S), the source's voltage
  readonly i2c: Bus;
  readonly sda: string; // the pins its I²C is on
  readonly scl: string;
  readonly time: number; // s since reset
  onSerial: ((text: string) => void) | null;
  runUntil(time: number): void;
  initial(): [string, Mode][]; // every pin as it is now
  take(): PinChange[]; // the pins' changes since the last take
  sense(pin: string, volts: number): void;
  send(text: string): void; // to its serial port
  readonly led?: boolean; // an LED on the board (the Pico's, on GP25)
  // the pins nothing in the circuit follows (Session: on a node of their own): their changes may be left out
  // of take() — the circuit gets them as they are (initial()) once a slice (an I²S clock on a free pin)
  mute?(pins: ReadonlySet<string>): void;
}
