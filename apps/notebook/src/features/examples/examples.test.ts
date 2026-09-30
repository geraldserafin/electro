// Every sketch in the courses and examples compiles with the in-page compiler (and runs a moment
// on its board without the emulator stopping): a lesson whose program does not build is a broken
// lesson. Skipped when the compiler has not been built (scripts/make-arduino-*.sh).
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { Uno } from "@/features/simulation/arduino";
import { type Board, compile, type Toolchain, toolchain } from "@/features/simulation/compiler/toolchain";
import { Backpack, Oled } from "@/features/simulation/i2c";
import { Pico } from "@/features/simulation/pico";
import type { Notebook } from "@/shared/model/types";

const dir = new URL("../../../public/arduino/", import.meta.url);
const examples = new URL("../../../examples/", import.meta.url);
const built = (sysroot: string) => existsSync(new URL("llvm.json", dir)) && existsSync(new URL(sysroot, dir));
const read = (name: string) => readFileSync(new URL(name, dir));
const buffer = (b: Buffer) => b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength) as ArrayBuffer;

async function load(board: Board, sysroot: string): Promise<Toolchain> {
  const { modules: names } = JSON.parse(read("llvm.json").toString()) as { modules: string[] };
  const { instantiate } = await import(/* @vite-ignore */ new URL("llvm.js", dir).href);
  const modules = Object.fromEntries(
    await Promise.all(names.map(async (n) => [n, await WebAssembly.compile(read(n))] as const)),
  );
  return toolchain(
    { instantiate, modules, clangHeaders: buffer(read("clang-headers.tar")), sysroot: buffer(read(sysroot)) },
    board,
  );
}

/** Each board's sketch: where it is, which board, its text. */
const sketches = readdirSync(examples, { withFileTypes: true })
  .filter((d) => d.isDirectory())
  .flatMap((d) =>
    readdirSync(new URL(`${d.name}/`, examples))
      .filter((f) => f.endsWith(".electro.json"))
      .flatMap((f) => {
        const nb = JSON.parse(readFileSync(new URL(`${d.name}/${f}`, examples), "utf8")) as Notebook;
        return nb.cells.flatMap((c) =>
          c.type === "schematic"
            ? c.schematic.elements
                .filter((e) => (e.kind === "arduino" || e.kind === "pico") && e.text)
                .map((e) => ({
                  where: `${d.name}/${f} ${c.name} ${e.id}`,
                  board: (e.kind === "pico" ? "pico" : "uno") as Board,
                  text: e.text!,
                }))
            : [],
        );
      }),
  );

for (const [board, sysroot] of [
  ["uno", "sysroot.tar"],
  ["pico", "pico.tar"],
] as const) {
  const mine = sketches.filter((s) => s.board === board);
  describe.skipIf(!built(sysroot) || !mine.length)(`the examples' ${board} sketches`, () => {
    let app: Promise<Toolchain> | null = null;
    it.each(mine.map((s) => [s.where, s.text]))(
      "%s",
      async (_, text) => {
        app ??= load(board, sysroot);
        const result = await compile(await app, text);
        if ("failed" in result) expect.fail(result.failed);
        if (!("hex" in result || "image" in result)) expect.fail(JSON.stringify(result));
        if ("image" in result) {
          new Pico(result.image).runUntil(0.02);
          return;
        }
        // an Uno with the displays the examples use on its I²C bus: whatever it draws or prints shows
        const uno = new Uno(result.hex);
        const oled = new Oled("OLED_1", 0x3c, () => true);
        const lcd = new Backpack("LCD_1", 0x27, () => true);
        uno.i2c.devices.push(oled, lcd);
        uno.runUntil(text.includes("SSD1306") || text.includes("LiquidCrystal_I2C") ? 1.5 : 0.05);
        if (text.includes("SSD1306"))
          expect(oled.pixels().rows.flat().filter(Boolean).length, "the OLED shows something").toBeGreaterThan(20);
        if (text.includes("LiquidCrystal_I2C"))
          expect(lcd.screen().text.flat().join("").trim(), "the LCD shows something").not.toBe("");
      },
      120_000,
    );
  });
}
