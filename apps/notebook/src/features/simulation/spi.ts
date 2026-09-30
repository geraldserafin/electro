// SPI between an emulated Pico and the devices on it: the emulator hands over each byte its SPI sends
// (not SCK's and MOSI's levels, some tens of MHz), so the bus is here, in the page, like I²C's
// (i2c.ts). A device knows by the chip's own pins wired to its CS and D/C whether a byte is its own
// and whether it is a command: it asks the chip (Chip.level) as the byte comes.
import { Ili9341 } from "./tft";
import type { Board, Session } from "./session";

export interface SpiDevice {
  transmit(byte: number): void;
}

/** One of the chip's SPIs: the pins its SCK and TX (MOSI) can be on, and the devices on them. */
export class Spi {
  devices: SpiDevice[] = [];

  constructor(readonly sck: readonly string[], readonly tx: readonly string[]) {}

  transmit(byte: number) {
    for (const d of this.devices) d.transmit(byte);
  }
}

/** A chip whose SPI a device can be on, and how it drives a pin: level(pin)() — high now? */
export interface SpiChip {
  readonly spi: Spi[];
  level(pin: string): () => boolean;
}

export const hasSpi = (chip: object): chip is SpiChip => "spi" in chip && "level" in chip;

// electro.devices.ILI9341's pins, in order
const VCC = 0, GND = 1, CS = 2, RESET = 3, DC = 4, MOSI = 5, SCK = 6, LED = 7;

/**
 * Hands each SPI of ``board``'s chip the displays on it: those whose SCK and MOSI are wired to pins the
 * chip has that SPI's on; their CS, RESET and D/C are read from the chip's pins they are wired to (not
 * wired to one: CS held low, RESET high). ``kept``: the displays made so far, by id — reused, so a
 * display keeps what it showed across a new program.
 */
export function spiDevicesOn(s: Session, board: Board, kept: Map<string, Ili9341>) {
  const chip = board.chip;
  if (!hasSpi(chip)) return;
  const { pins, program } = s.circuit;
  const pinOf = new Map<string, string>(); // node → the chip's pin on it
  for (const [pin, node] of Object.entries(board.pins)) if (node && !pinOf.has(node)) pinOf.set(node, pin);
  for (const spi of chip.spi) spi.devices = [];
  for (const [id, kind] of Object.entries(program.kinds)) {
    if (kind !== "ILI9341") continue;
    const at = (i: number) => pins[id]?.[i] ?? null;
    const on = (i: number) => {
      const node = at(i);
      return node ? pinOf.get(node) ?? null : null;
    };
    const sck = on(SCK), mosi = on(MOSI);
    const spi = chip.spi.find((p) => sck && mosi && p.sck.includes(sck) && p.tx.includes(mosi));
    if (!spi) continue;
    const volts = (i: number) => s.sim.node(at(i) ?? "") - s.sim.node(at(GND) ?? "");
    const [cs, reset, dc] = [on(CS), on(RESET), on(DC)].map((pin) => (pin ? chip.level(pin) : null));
    let checked = -1, powered = false; // (the supply looked at once a step of the circuit's, not for every byte)
    let tft = kept.get(id);
    if (!tft) kept.set(id, (tft = new Ili9341(id)));
    tft.wire({
      powered: () => {
        if (s.sim.t !== checked) [checked, powered] = [s.sim.t, volts(VCC) > 2.5];
        return powered;
      },
      selected: () => (cs ? !cs() : true),
      reset: () => (reset ? !reset() : false),
      data: () => (dc ? dc() : true),
      backlight: () => Math.max(0, Math.min(1, (volts(LED) - 1.8) / 1.2)),
    });
    spi.devices.push(tft);
  }
}
