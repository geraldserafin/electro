// A Raspberry Pi Pico in the page: its RP2040 emulated, both cores (@electro/rp2040js), boots from its
// bootrom the flash image the server compiled (arduino-pico: boot stage 2 first) or one given whole (a
// UF2), and its pins meet the circuit as an Uno's do (chip.ts). Serial is its USB (a host is emulated
// too), Serial1 its UART0; Wire is I²C0 on GP4 (SDA) and GP5 (SCL), as arduino-pico has them; its two
// SPIs hand their bytes to the devices on them (spi.ts).
//
// When the program keeps both cores busy (Doom) the emulator cannot keep up with a real one: then the
// cores run as if clocked slower (``pace``) — the circuit's time, the timers, PWM, the UARTs keep
// theirs, only fewer instructions fit in a second — rather than everything falling behind.
import { ConsoleLogger, GPIOPinState, I2CMode, LogLevel, RP2040, USBCDC } from "@electro/rp2040js";
import type { Chip, Mode, PinChange } from "./chip";
import { Bus } from "./i2c";
import { Spi } from "./spi";

// electro.devices.PICO_PINS: GP0–GP22, GP26–GP28 (ADC0–2)
const PINS = [...Array.from({ length: 23 }, (_, i) => i), 26, 27, 28];
const LED = 25; // on the board, not a pin
// an input reads LOW below 0.8 V and HIGH above 2.0 V; in between it keeps what it read (Schmitt trigger)
const LOW_BELOW = 0.8, HIGH_ABOVE = 2.0, VDD = 3.3;
// the share of the page's time the cores may take (the circuit, the rest of the page need theirs), and
// how much of the circuit's time is measured before the pace is set again
const SHARE = 0.7, WINDOW = 0.1;
const SLOWEST = 0.01;

const MODE: Record<GPIOPinState, Mode> = {
  [GPIOPinState.Low]: "low", [GPIOPinState.High]: "high", [GPIOPinState.Input]: "input",
  [GPIOPinState.InputPullUp]: "pullup", [GPIOPinState.InputPullDown]: "pulldown",
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
  readonly spi: Spi[];
  onSerial: ((text: string) => void) | null = null;
  led = false;
  /** How fast the cores run, of their clock: 1 while the emulator keeps up. */
  pace = 1;
  /** Whether the pace follows how long the runs take (a test sets it false: its runs need not keep up). */
  adaptive = true;
  private mcu = new RP2040();
  private changes: PinChange[] = [];
  private read = new Map<number, boolean>(); // what each input reads now (for the hysteresis)
  private high = new Uint8Array(30); // each GPIO driven high now (kept by its listener: asked for every SPI byte)
  private cdc: USBCDC;
  private decoder = new TextDecoder();
  private measured = { wall: 0, time: 0 }; // ms taken, s run, since the pace was last set

  constructor(image: Uint8Array) {
    const mcu = this.mcu;
    mcu.logger = new ConsoleLogger(LogLevel.Error);
    mcu.flash.set(image);
    mcu.reset(); // the bootrom starts it from the flash
    for (const i of PINS) {
      this.high[i] = mcu.gpio[i].value === GPIOPinState.High ? 1 : 0;
      mcu.gpio[i].addListener((state) => {
        this.high[i] = state === GPIOPinState.High ? 1 : 0;
        this.changes.push({ time: this.time, pin: `GP${i}`, mode: MODE[state] });
      });
    }
    mcu.gpio[LED].addListener((state) => (this.led = state === GPIOPinState.High));
    this.cdc = new USBCDC(mcu.usbCtrl);
    this.cdc.onSerialData = (bytes, length) => this.onSerial?.(this.decoder.decode(bytes.subarray(0, length), { stream: true })); // (a scratch buffer)
    mcu.uart[0].onByte = (byte) => this.onSerial?.(String.fromCharCode(byte));
    const i2c = mcu.i2c[0], bus = (this.i2c = new Bus(i2c));
    i2c.onStart = () => bus.start();
    i2c.onConnect = (address, mode) => bus.connectToSlave(address, mode === I2CMode.Write);
    i2c.onWriteByte = (value) => bus.writeByte(value);
    i2c.onReadByte = () => bus.readByte();
    i2c.onStop = () => bus.stop();
    // SPI0 on GP2/6/18/22 (SCK) and GP3/7/19 (TX), SPI1 on GP10/14/26 and GP11/15/27
    this.spi = [
      new Spi(["GP2", "GP6", "GP18", "GP22"], ["GP3", "GP7", "GP19"]),
      new Spi(["GP10", "GP14", "GP26"], ["GP11", "GP15", "GP27"]),
    ];
    mcu.spi.forEach((port, n) => {
      port.onTransmit = (value) => {
        this.spi[n].transmit(value);
        port.completeTransmit(0); // (nothing drives MISO back)
      };
    });
  }

  get time(): number {
    return this.mcu.clock.nanos / 1e9;
  }

  /** The clock the cores run at now, in Hz: the firmware's, times the pace. */
  get frequency(): number {
    return this.mcu.clkSys * this.pace;
  }

  initial(): [string, Mode][] {
    return PINS.map((i) => [`GP${i}`, MODE[this.mcu.gpio[i].value]]);
  }

  take(): PinChange[] {
    const changes = this.changes;
    this.changes = [];
    return changes;
  }

  /** Whether the chip drives ``pin`` high, asked when wanted (for a device that samples a pin as each byte comes: SPI's DC). */
  level(pin: string): () => boolean {
    const i = Number(pin.slice(2)), high = this.high;
    return () => high[i] === 1;
  }

  /** Run the program up to ``time`` (s since reset); both cores asleep (WFE, WFI), the clock jumps to what wakes them. */
  runUntil(time: number) {
    const mcu = this.mcu, clock = mcu.clock, [core0, core1] = mcu.core;
    const end = time * 1e9, from = clock.nanos, started = performance.now();
    const nanosPerCycle = 1e9 / (mcu.clkSys * this.pace);
    while (clock.nanos < end) {
      if (core0.waiting && core1.waiting) {
        const alarm = clock.nanosToNextAlarm; // (0: none set)
        clock.tick(alarm > 0 ? Math.min(alarm, end - clock.nanos) : end - clock.nanos);
        continue;
      }
      const cycles = mcu.stepCores();
      if (mcu.pioActiveSmCount) mcu.stepPios(cycles);
      clock.tick(cycles * nanosPerCycle);
    }
    if (this.adaptive) this.adapt(performance.now() - started, (clock.nanos - from) / 1e9);
  }

  /** After a run of ``wall`` ms for ``time`` s: slower if it took more than its share of the time, faster (up to the clock) if less. */
  private adapt(wall: number, time: number) {
    const m = this.measured;
    m.wall += wall;
    m.time += time;
    if (m.time < WINDOW) return;
    const share = m.wall / 1000 / m.time; // of real time, at the pace it ran
    const wanted = Math.min(1, Math.max(SLOWEST, (this.pace * SHARE) / Math.max(share, 1e-6)));
    this.pace = Math.min(1, this.pace * 0.5 + wanted * 0.5);
    this.measured = { wall: 0, time: 0 };
  }

  /** What the circuit puts on a pin: for digitalRead(), and on GP26–GP28 for analogRead(). */
  sense(pin: string, volts: number) {
    const i = Number(pin.slice(2));
    const was = this.read.get(i) ?? false;
    const high = volts > HIGH_ABOVE ? true : volts < LOW_BELOW ? false : was;
    if (high !== was || !this.read.has(i)) {
      this.read.set(i, high);
      this.mcu.gpio[i].setInputValue(high);
    }
    if (i >= 26) this.mcu.adc.channelValues[i - 26] = Math.round(Math.max(0, Math.min(1, volts / VDD)) * 4095);
  }

  /** Text for Serial.read() (the USB) and Serial1.read() (UART0). */
  send(text: string) {
    for (const byte of new TextEncoder().encode(text)) {
      this.cdc.sendSerialByte(byte);
      this.mcu.uart[0].feedByte(byte);
    }
  }
}
