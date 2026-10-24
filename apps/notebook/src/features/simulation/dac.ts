// An MCP4822 on a Pico's SPI (spi.ts): a dual 12-bit DAC. Each 16-bit word — sent whole, or as two bytes —
// says which output (bit 15), the gain (bit 13: 1×, else 2×), whether it is on (bit 12) and the code
// (bits 11–0): that output goes to code / 4096 · 2.048 V · gain in the circuit at the moment the word came
// (LDAC held low: as CS goes up after it — a word takes well under a microsecond).

import type { SpiDevice } from "./spi";

const VREF = 2.048;

export interface DacWiring {
  selected: () => boolean; // its CS low
  powered: () => number; // its supply's voltage (an output goes no higher)
  set: (channel: 0 | 1, volts: number) => void;
}

export class Mcp4822 implements SpiDevice {
  private wiring: DacWiring | null = null;
  private first: number | null = null; // a word's first byte, its second to come

  wire(wiring: DacWiring) {
    this.wiring = wiring;
    this.first = null;
  }

  transmit(value: number, bits = 8) {
    const w = this.wiring;
    if (!w?.selected()) {
      this.first = null;
      return;
    }
    if (bits > 8) this.word(value);
    else if (this.first === null) this.first = value;
    else {
      this.word((this.first << 8) | value);
      this.first = null;
    }
  }

  transmitMany(memory: DataView, offset: number, count: number, size: number, mask: number) {
    const bits = Math.round(Math.log2(mask + 1));
    for (let i = 0; i < count; i++)
      this.transmit(
        size === 2 ? memory.getUint16(offset + 2 * i, true) & mask : memory.getUint8(offset + i) & mask,
        bits,
      );
  }

  private word(w: number) {
    const wiring = this.wiring!;
    const gain = w & 0x2000 ? 1 : 2,
      on = (w & 0x1000) !== 0;
    const volts = on ? Math.min(wiring.powered(), ((w & 0xfff) / 4096) * VREF * gain) : 0;
    wiring.set(w & 0x8000 ? 1 : 0, Math.max(0, volts));
  }
}
