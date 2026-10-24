// The MCP4822's words (dac.ts) and a speaker listened to (peripherals.ts: hear, played).
import { describe, expect, test } from "vitest";
import { Mcp4822 } from "./dac";
import { AUDIO_RATE, hear, hearing, played } from "./peripherals";

function dac(selected = () => true) {
  const set: [number, number][] = [];
  const d = new Mcp4822();
  d.wire({ selected, powered: () => 3.3, set: (channel, volts) => set.push([channel, volts]) });
  return { d, set };
}

describe("MCP4822", () => {
  test("a 16-bit word sets its output: code / 4096 · 2.048 V, times the gain", () => {
    const { d, set } = dac();
    d.transmit(0x3000 | 2048, 16); // A, 1×, on: half of 2.048 V
    d.transmit(0x9000 | 4095, 16); // B, 2×: 4.095 V, but no more than its supply
    d.transmit(0x2000 | 4095, 16); // A off
    expect(set).toEqual([
      [0, 1.024],
      [1, 3.3],
      [0, 0],
    ]);
  });

  test("two bytes make a word; a word not its own (CS high) is not taken", () => {
    let cs = true;
    const { d, set } = dac(() => cs);
    d.transmit(0x30);
    d.transmit(0x00);
    cs = false;
    d.transmit(0x3f);
    cs = true;
    d.transmit(0x30);
    d.transmit(0x01);
    expect(set).toEqual([
      [0, 0],
      [0, 2.048 / 4096],
    ]);
  });
});

describe("speaker", () => {
  test("it hears each sample's mean, its DC gone", () => {
    const h = hearing("LS_1", 0, 0);
    const period = 1 / AUDIO_RATE;
    // a square wave of 1 kHz around 1 V, in steps not on the samples' edges
    for (let k = 0; k < 2000; k++)
      hear(h, 1 + (Math.floor(k / 16) % 2 ? 0.5 : -0.5), k * 0.03125e-3, (k + 1) * 0.03125e-3);
    const out = played(h);
    expect(out.length).toBe(Math.floor((2000 * 0.03125e-3) / period));
    const tail = out.slice(-640);
    expect(Math.max(...tail)).toBeGreaterThan(0.2);
    expect(Math.abs(tail.reduce((a, b) => a + b, 0) / tail.length)).toBeLessThan(0.02);
  });
});
