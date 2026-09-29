// A Raspberry Pi Pico in the page: its RP2040 emulated by rp2040js (one core, at the clock the
// firmware sets) runs the program the server compiled (arduino-pico: a flash image, boot stage 2
// first), and its pins meet the circuit as an Uno's do (chip.ts). Serial is its USB (a host is
// emulated too), Serial1 its UART0; Wire is I²C0 on GP4 (SDA) and GP5 (SCL), as arduino-pico has them.
import { ConsoleLogger, GPIOPinState, I2CMode, LogLevel, Simulator, USBCDC } from "rp2040js";
import { bootromB1 } from "./bootrom";
import type { Chip, Mode, PinChange } from "./chip";
import { Bus } from "./i2c";

// electro.devices.PICO_PINS: GP0–GP22, GP26–GP28 (ADC0–2)
const PINS = [...Array.from({ length: 23 }, (_, i) => i), 26, 27, 28];
const LED = 25; // on the board, not a pin
// an input reads LOW below 0.8 V and HIGH above 2.0 V; in between it keeps what it read (Schmitt trigger)
const LOW_BELOW = 0.8, HIGH_ABOVE = 2.0, VDD = 3.3;

const MODE: Record<GPIOPinState, Mode> = {
  [GPIOPinState.Low]: "low", [GPIOPinState.High]: "high", [GPIOPinState.Input]: "input",
  [GPIOPinState.InputPullUp]: "pullup", [GPIOPinState.InputPullDown]: "pulldown",
  [GPIOPinState.InputBusKeeper]: "input", // (it holds what it reads: near enough an input)
};

export class Pico implements Chip {
  readonly pins = PINS.map((i) => `GP${i}`);
  /** electro.devices.PICO_MODES */
  readonly modes: Record<Mode, [number, number]> = {
    input: [1e-8, 0], pullup: [1 / 50000, VDD], pulldown: [1 / 50000, 0], low: [1 / 40, 0], high: [1 / 40, VDD],
  };
  readonly sda = "GP4";
  readonly scl = "GP5";
  readonly i2c: Bus;
  onSerial: ((text: string) => void) | null = null;
  led = false;
  private sim = new Simulator();
  private changes: PinChange[] = [];
  private read = new Map<number, boolean>(); // what each input reads now (for the hysteresis)
  private cdc: USBCDC;
  private decoder = new TextDecoder();

  constructor(image: Uint8Array) {
    const mcu = this.sim.rp2040;
    mcu.logger = new ConsoleLogger(LogLevel.Error);
    mcu.loadBootrom(bootromB1);
    mcu.flash.set(image);
    mcu.core.PC = 0x10000000; // boot stage 2, at the start of the flash: it sets up the flash and jumps on
    for (const i of PINS) mcu.gpio[i].addListener((state) => this.changes.push({ time: this.time, pin: `GP${i}`, mode: MODE[state] }));
    mcu.gpio[LED].addListener((state) => (this.led = state === GPIOPinState.High));
    this.cdc = new USBCDC(mcu.usbCtrl);
    this.cdc.onSerialData = (bytes) => this.onSerial?.(this.decoder.decode(bytes, { stream: true }));
    mcu.uart[0].onByte = (byte) => this.onSerial?.(String.fromCharCode(byte));
    const i2c = mcu.i2c[0], bus = (this.i2c = new Bus(i2c));
    i2c.onStart = () => bus.start();
    i2c.onConnect = (address, mode) => bus.connectToSlave(address, mode === I2CMode.Write);
    i2c.onWriteByte = (value) => bus.writeByte(value);
    i2c.onReadByte = () => bus.readByte();
    i2c.onStop = () => bus.stop();
  }

  get time(): number {
    return this.sim.clock.nanos / 1e9;
  }

  initial(): [string, Mode][] {
    return PINS.map((i) => [`GP${i}`, MODE[this.sim.rp2040.gpio[i].value]]);
  }

  take(): PinChange[] {
    const changes = this.changes;
    this.changes = [];
    return changes;
  }

  /** Run the program up to ``time`` (s since reset); asleep (WFE, WFI), the clock jumps to what wakes it. */
  runUntil(time: number) {
    const { clock, rp2040: mcu } = this.sim, core = mcu.core;
    const end = time * 1e9, cycle = 1e9 / mcu.clkSys;
    while (clock.nanos < end) {
      if (core.waiting) clock.tick(Math.max(1, Math.min(clock.nanosToNextAlarm, end - clock.nanos)));
      else clock.tick(core.executeInstruction() * cycle);
    }
  }

  /** What the circuit puts on a pin: for digitalRead(), and on GP26–GP28 for analogRead(). */
  sense(pin: string, volts: number) {
    const i = Number(pin.slice(2));
    const was = this.read.get(i) ?? false;
    const high = volts > HIGH_ABOVE ? true : volts < LOW_BELOW ? false : was;
    if (high !== was || !this.read.has(i)) {
      this.read.set(i, high);
      this.sim.rp2040.gpio[i].setInputValue(high);
    }
    if (i >= 26) this.sim.rp2040.adc.channelValues[i - 26] = Math.round(Math.max(0, Math.min(1, volts / VDD)) * 4095);
  }

  /** Text for Serial.read() (the USB) and Serial1.read() (UART0). */
  send(text: string) {
    for (const byte of new TextEncoder().encode(text)) {
      this.cdc.sendSerialByte(byte);
      this.sim.rp2040.uart[0].feedByte(byte);
    }
  }
}
