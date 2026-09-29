// An Arduino Uno in the page: its ATmega328P emulated by avr8js runs the compiled sketch (Intel HEX),
// and its pins meet the circuit. Each pin the chip drives becomes a source with a resistance in the
// circuit (electro.devices.PIN_MODES); what the circuit puts on the pins is what digitalRead() and
// analogRead() see.
import {
  AVRADC, AVRIOPort, AVRTimer, AVRTWI, AVRUSART, CPU, PinState, adcConfig, avrInstruction, portBConfig, portCConfig,
  portDConfig, timer0Config, timer1Config, timer2Config, twiConfig, usart0Config,
} from "avr8js";
import { Bus } from "./i2c";

export const CLOCK = 16e6; // Hz
// an input reads LOW below 0.3·Vcc and HIGH above 0.6·Vcc; in between it keeps what it read (ATmega328P)
const LOW_BELOW = 1.5, HIGH_ABOVE = 3.0;

// Uno's pins: D0–D7 on port D, D8–D13 on port B, A0–A5 on port C
const PINS: { name: string; port: "B" | "C" | "D"; bit: number }[] = [
  ...Array.from({ length: 8 }, (_, i) => ({ name: `D${i}`, port: "D" as const, bit: i })),
  ...Array.from({ length: 6 }, (_, i) => ({ name: `D${8 + i}`, port: "B" as const, bit: i })),
  ...Array.from({ length: 6 }, (_, i) => ({ name: `A${i}`, port: "C" as const, bit: i })),
];

/** electro.devices.PIN_MODES: (conductance to the pin's source, the source's voltage). */
export const PIN_MODES: Record<PinState, [number, number]> = {
  [PinState.Input]: [1e-8, 0],
  [PinState.InputPullUp]: [1 / 35000, 5],
  [PinState.Low]: [1 / 25, 0],
  [PinState.High]: [1 / 25, 5],
};

/** A pin that changed: at which CPU cycle, which pin (``D13``), to what. */
export interface PinEvent {
  cycle: number;
  pin: string;
  state: PinState;
}

/** Intel HEX → the flash, as the CPU wants it (16-bit words). */
export function loadHex(source: string): Uint16Array {
  const flash = new Uint8Array(0x8000);
  let base = 0;
  for (const line of source.split(/\r?\n/)) {
    if (!line.startsWith(":")) continue;
    const bytes = line.slice(1).match(/../g)!.map((h) => parseInt(h, 16));
    const [count, hi, lo, type] = bytes;
    if (type === 0) flash.set(bytes.slice(4, 4 + count), base + ((hi << 8) | lo));
    else if (type === 2) base = ((bytes[4] << 8) | bytes[5]) << 4;
    else if (type === 4) base = ((bytes[4] << 8) | bytes[5]) << 16;
  }
  return new Uint16Array(flash.buffer);
}

export class Uno {
  readonly cpu: CPU;
  private ports: Record<"B" | "C" | "D", AVRIOPort>;
  private adc: AVRADC;
  private last = new Map<string, PinState>();
  private read = new Map<string, boolean>(); // what each input reads now (for the hysteresis)
  private usart: AVRUSART;
  private incoming: number[] = []; // bytes typed into the serial monitor, not yet received
  /** Pin changes not yet taken by the circuit, in order. */
  events: PinEvent[] = [];
  onSerial: ((text: string) => void) | null = null;
  /** Its I²C (A4 SDA, A5 SCL): the devices on it answer the TWI's transactions (i2c.ts). */
  readonly i2c: Bus;

  constructor(hex: string) {
    this.cpu = new CPU(loadHex(hex));
    new AVRTimer(this.cpu, timer0Config); // millis(), delay()
    new AVRTimer(this.cpu, timer1Config);
    new AVRTimer(this.cpu, timer2Config);
    const usart = (this.usart = new AVRUSART(this.cpu, usart0Config, CLOCK));
    usart.onByteTransmit = (byte) => this.onSerial?.(String.fromCharCode(byte));
    usart.onRxComplete = () => this.receive();
    this.adc = new AVRADC(this.cpu, adcConfig);
    const twi = new AVRTWI(this.cpu, twiConfig, CLOCK);
    twi.eventHandler = this.i2c = new Bus(twi);
    this.ports = {
      B: new AVRIOPort(this.cpu, portBConfig),
      C: new AVRIOPort(this.cpu, portCConfig),
      D: new AVRIOPort(this.cpu, portDConfig),
    };
    for (const port of Object.values(this.ports)) port.addListener(() => this.scan());
    for (const { name } of PINS) this.last.set(name, PinState.Input);
  }

  /** Every pin as it is now (all inputs before the sketch starts). */
  states(): [string, PinState][] {
    return PINS.map(({ name, port, bit }) => [name, this.ports[port].pinState(bit)]);
  }

  private scan() {
    for (const { name, port, bit } of PINS) {
      const state = this.ports[port].pinState(bit);
      if (state !== this.last.get(name)) {
        this.last.set(name, state);
        this.events.push({ cycle: this.cpu.cycles, pin: name, state });
      }
    }
  }

  get time(): number {
    return this.cpu.cycles / CLOCK;
  }

  /** Bytes for Serial.read(): received one by one at the sketch's baud rate (once Serial.begin() ran). */
  send(text: string) {
    this.incoming.push(...new TextEncoder().encode(text));
    this.receive();
  }

  private receive() {
    if (this.incoming.length && !this.usart.rxBusy && this.usart.writeByte(this.incoming[0])) this.incoming.shift();
  }

  /** Run the sketch up to ``time`` (seconds since reset). */
  runUntil(time: number) {
    this.receive(); // Serial.begin() may have come since
    const end = time * CLOCK;
    const { cpu } = this;
    while (cpu.cycles < end) {
      avrInstruction(cpu);
      cpu.tick();
    }
  }

  /** What the circuit puts on a pin: its voltage, for digitalRead() and, on A0–A5, analogRead(). */
  sense(pin: string, volts: number) {
    const p = PINS.find((x) => x.name === pin);
    if (!p) return;
    const was = this.read.get(pin) ?? false;
    const high = volts > HIGH_ABOVE ? true : volts < LOW_BELOW ? false : was;
    this.read.set(pin, high);
    this.ports[p.port].setPin(p.bit, high);
    if (p.port === "C") this.adc.channelValues[p.bit] = Math.max(0, Math.min(5, volts));
  }

  static readonly pins = PINS.map((p) => p.name);
}
