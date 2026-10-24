// The block JIT (@electro/rp2040js's jit.ts) against the interpreter it stands in for: real programs run with
// every block checked — run, undone, run again by the interpreter, the two compared (BlockJit.verifying).
import { readFileSync } from "node:fs";
import { BlockJit, RP2040 } from "@electro/rp2040js";
import { expect, test } from "vitest";

function run(file: string, seconds: number) {
  const mcu = new RP2040();
  mcu.flash.set(new Uint8Array(readFileSync(new URL(`./fixtures/${file}`, import.meta.url))));
  mcu.reset();
  for (let pin = 0; pin < 30; pin++) mcu.gpio[pin].setInputValue(true); // (buttons released: pulled up)
  // something on I²C that acknowledges everything (the OLED, for the raycaster: Wire takes its other way on a NACK)
  const i2c = mcu.i2c[0];
  i2c.onStart = () => i2c.completeStart();
  i2c.onConnect = () => i2c.completeConnect(true);
  i2c.onWriteByte = () => i2c.completeWrite(true);
  i2c.onReadByte = () => i2c.completeRead(0xff);
  i2c.onStop = () => i2c.completeStop();
  const set = (pin: number, at: number, high: boolean) =>
    mcu.clock.createAlarm({ fire: () => mcu.gpio[pin].setInputValue(high) }).schedule(at * 1e9);
  if (file.startsWith("hell")) {
    set(14, 0.3, false); // FIRE pressed and let go: the game starts
    set(14, 0.5, true);
    set(10, 0.6, false); // walking on
  }
  const [core0, core1] = mcu.core,
    jits = [new BlockJit(core0), new BlockJit(core1)];
  for (const j of jits) j.verifying = true;
  const clock = mcu.clock;
  while (clock.nanos < seconds * 1e9) {
    // (as Pico.runUntil steps them)
    if (core0.waiting && core1.waiting) {
      const alarm = clock.nanosToNextAlarm;
      clock.tick(alarm > 0 ? alarm : seconds * 1e9 - clock.nanos);
      continue;
    }
    const start = core0.cycles;
    mcu.currentCore = 0;
    if (core0.waiting) core0.cycles = Math.max(core0.cycles, core1.cycles) + 1;
    else jits[0].step();
    mcu.currentCore = 1;
    while (core1.cycles < core0.cycles) {
      if (core1.waiting) {
        core1.cycles = core0.cycles;
        break;
      }
      jits[1].step();
    }
    clock.tick(((core0.cycles - start) * 1e9) / mcu.clkSys);
    for (const j of jits) if (j.mismatch) return { mismatch: j.mismatch, jits };
  }
  return { mismatch: null, jits };
}

test("a sketch (arduino-pico, blink): every block as the interpreter runs it", () => {
  const { mismatch, jits } = run("blink.pico.bin", 0.3);
  expect(mismatch).toBeNull();
  expect(jits[0].stats.blocks).toBeGreaterThan(1000);
});

test("the raycaster (hell.pico.ino: arithmetic, I²C, the OLED): every block as the interpreter runs it", () => {
  const { mismatch, jits } = run("hell.pico.bin", 1.2);
  expect(mismatch).toBeNull();
  expect(jits[0].stats.translated).toBeGreaterThan(100);
}, 120_000);

// ADD Rd, PC (a Thumb jump table: add r0, pc; ldrb r0, [r0, #4]; lsls r0, #1; add pc, r0): the PC read as the
// instruction's address + 4, by the interpreter and by a block alike
test("add r0, pc reads the PC as its address + 4", () => {
  const mcu = new RP2040();
  const core = mcu.core[0],
    at = 0x20000100;
  mcu.writeUint16(at, 0x4478); // add r0, pc
  mcu.writeUint16(at + 2, 0xe7fe); // b . (the block ends)
  const from = (run: () => void) => {
    core.registers[0] = 0x10;
    core.PC = at;
    run();
    return core.registers[0] >>> 0;
  };
  expect(from(() => core.executeInstruction())).toBe(at + 4 + 0x10);
  const jit = new BlockJit(core);
  expect(from(() => jit.step())).toBe(at + 4 + 0x10);
});
