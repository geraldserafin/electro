// The ILI9341 as Adafruit_ILI9341 and Doom drive it, a firmware file's flash, and Doom itself on a Pico
// in a circuit (fixtures/tft.live.json; public/pico/doom.bin, built by make-pico-doom.sh).
import { readFileSync } from "node:fs";
import { describe, expect, test } from "vitest";
import { firmwareFile, uf2Flash } from "./firmware";
import { Pico } from "./pico";
import { Runner } from "./runner";
import { HEIGHT, Ili9341, WIDTH } from "./tft";

function wired(tft: Ili9341, lines = { powered: true, selected: true, reset: false, data: true, backlight: 1 }) {
  tft.wire({ powered: () => lines.powered, selected: () => lines.selected, reset: () => lines.reset, data: () => lines.data, backlight: () => lines.backlight });
  const send = (command: number, ...params: number[]) => {
    lines.data = false;
    tft.transmit(command);
    lines.data = true;
    for (const p of params) tft.transmit(p);
  };
  return { lines, send };
}
const at = (image: Uint8ClampedArray, x: number, y: number) => Array.from(image.slice((y * WIDTH + x) * 4, (y * WIDTH + x) * 4 + 3));

describe("an ILI9341", () => {
  test("blank until it is woken and switched on; then what was written, landscape (MV) and BGR as Adafruit sets it", () => {
    const tft = new Ili9341("TFT_1"), { send } = wired(tft);
    expect(tft.data().shown).toBe(false);
    send(0x11); // SLPOUT
    send(0x29); // DISPON
    send(0x36, 0x28); // MADCTL: MV | BGR
    send(0x2a, 0, 10, 0, 11); // columns 10–11 (x, landscape)
    send(0x2b, 0, 20, 0, 20); // page 20 (y)
    send(0x2c, 0xf8, 0x00, 0x00, 0x1f); // red, then blue
    expect(tft.data().shown).toBe(true);
    expect(tft.picture(false)).toBeNull(); // (a small window, not a frame drawn whole: only when asked anyway)
    const image = tft.picture(true);
    expect(at(image!, 10, 20)).toEqual([255, 0, 0]);
    expect(at(image!, 11, 20)).toEqual([0, 0, 255]);
    expect(at(image!, 12, 20)).toEqual([0, 0, 0]);
    expect(tft.picture(true)).toBeNull(); // nothing new since
  });

  test("a frame written whole (Doom's 320 × 200 window): its picture as it was then, not the next half written", () => {
    const tft = new Ili9341("TFT_1"), { send } = wired(tft);
    send(0x11); send(0x29); send(0x36, 0x28);
    send(0x2a, 0, 0, 0x01, 0x3f); // columns 0–319
    send(0x2b, 0, 20, 0, 219); // pages 20–219
    const pixels = (hi: number, count: number) => { for (let i = 0; i < count; i++) { tft.transmit(hi); tft.transmit(0); } };
    send(0x2c);
    pixels(0xf8, 320 * 200); // red, the whole frame
    send(0x2c);
    pixels(0x07, 320 * 100); // green, half the next
    expect(at(tft.picture(false)!, 0, 20)).toEqual([255, 0, 0]);
    expect(tft.picture(true)).toBeNull(); // (the next one half written: not yet, even asked anyway)
    pixels(0x07, 320 * 100);
    expect(at(tft.picture(false)!, 0, 219)).toEqual([0, 227, 0]);
  });

  test("RGB order (BGR clear) swaps red and blue; CS high: not its bytes; RESET: asleep again", () => {
    const tft = new Ili9341("TFT_1"), { lines, send } = wired(tft);
    send(0x11); send(0x29); send(0x36, 0x20); send(0x2a, 0, 0, 0, 0); send(0x2b, 0, 0, 0, 0);
    send(0x2c, 0xf8, 0x00);
    expect(at(tft.picture(true)!, 0, 0)).toEqual([0, 0, 255]);
    lines.selected = false;
    send(0x2c, 0x07, 0xe0); // (green, to someone else)
    lines.selected = true;
    expect(tft.picture(true)).toBeNull();
    lines.reset = true;
    tft.transmit(0);
    lines.reset = false;
    expect(tft.data().shown).toBe(false);
  });
});

describe("a firmware file", () => {
  test("named on the text's first line", () => {
    expect(firmwareFile("// firmware: /pico/doom.bin\n")).toBe("/pico/doom.bin");
    expect(firmwareFile("\n  //firmware:  x.uf2  \nvoid setup() {}")).toBe("x.uf2");
    expect(firmwareFile("void setup() {}\n// firmware: x.uf2")).toBeNull();
  });

  test("a UF2's blocks make the flash they write", () => {
    const block = (address: number, bytes: number[], n: number) => {
      const b = new Uint8Array(512), v = new DataView(b.buffer);
      v.setUint32(0, 0x0a324655, true); v.setUint32(4, 0x9e5d5157, true); v.setUint32(8, 0x2000, true);
      v.setUint32(12, 0x10000000 + address, true); v.setUint32(16, bytes.length, true);
      v.setUint32(20, n, true); v.setUint32(24, 2, true); v.setUint32(28, 0xe48bff56, true);
      b.set(bytes, 32); v.setUint32(508, 0x0ab16f30, true);
      return b;
    };
    const file = new Uint8Array(1024);
    file.set(block(0x100, [1, 2, 3], 0), 0);
    file.set(block(0, [9], 1), 512);
    const flash = uf2Flash(file);
    expect(flash.length).toBe(0x103);
    expect([flash[0], flash[1], flash[0x100], flash[0x102]]).toEqual([9, 0xff, 1, 3]);
  });
});

test("Doom on a Pico, the TFT on its SPI0: the title screen comes up", () => {
  const circuit = JSON.parse(readFileSync(new URL("./fixtures/tft.live.json", import.meta.url), "utf8"));
  const image = new Uint8Array(readFileSync(new URL("../../../public/pico/doom.bin", import.meta.url)));
  const runner = new Runner(circuit, []);
  runner.attach("PICO_1", { board: "pico", image });
  (runner.session.boards[0].chip as Pico).adaptive = false; // (a test's runs need not keep up)
  let picture: Uint8ClampedArray | null = null;
  for (let t = 0.1; t <= 2.0 && !picture; t += 0.1) {
    runner.advanceTo(t, 1e-3);
    const tft = runner.frame().tfts.TFT_1, image = runner.pictures(false)?.TFT_1;
    if (tft?.shown && tft.backlight > 0.9 && image) {
      // the title: mostly the red of its hellish sky (not the black it was cleared to)
      let red = 0;
      for (let i = 0; i < WIDTH * HEIGHT; i++) if (image[i * 4] > 120 && image[i * 4 + 2] < 90) red++;
      if (red > WIDTH * HEIGHT * 0.2) picture = image;
    }
  }
  expect(picture).not.toBeNull();
}, 120_000);
