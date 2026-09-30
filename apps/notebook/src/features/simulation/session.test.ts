// A circuit, a chip and a device in the page together (session.ts): an HC-SR04 on an Uno running
// fixtures/sonar.ino (pulseIn() on its echo). The circuit is fixtures/sonar.live.json
// (scripts/make_sim_fixtures.py); the sensor's timing is peripherals.ts's, scheduled as useLive does.
import { readFileSync } from "node:fs";
import { describe, expect, test } from "vitest";
import { Uno } from "./arduino";
import type { Chip, Mode, PinChange } from "./chip";
import { Backpack, modulesOn } from "./i2c";
import { ping, sonar } from "./peripherals";
import { Runner } from "./runner";
import { Session } from "./session";

const fixture = (name: string) => readFileSync(new URL(`./fixtures/${name}`, import.meta.url), "utf8");

function measure(distance: number) {
  const session = new Session(JSON.parse(fixture("sonar.live.json")));
  const board = session.attach("ARD_1", new Uno(fixture("sonar.hex")));
  let serial = "";
  board.chip.onSerial = (c) => (serial += c);
  const { sim } = session;
  const s = sonar("US_1", sim.program.parts.US_1.U_trig);
  session.advanceTo(0.1, 1e-4, () => {
    const echo = ping(s, sim.x[s.trig], sim.t, distance);
    if (!echo) return;
    session.schedule(echo[0], () => sim.setInput("US_1_echo", 1));
    session.schedule(echo[0] + echo[1], () => sim.setInput("US_1_echo", 0));
  });
  return serial.trim().split(/\s+/).map(Number);
}

// pulseIn() counts in a loop with interrupts on: millis()'s timer interrupt, every 1.024 ms, takes
// about 6 µs of it, so a long echo reads short by as much — on a real Uno too (0.6 %)
test.each([10, 100, 250])("pulseIn() measures the echo of %i cm as a real Uno does", (cm) => {
  const lengths = measure(cm);
  const echo = 2 * cm / 100 / 343 * 1e6, missed = 6.2 * Math.floor(echo / 1024);
  expect(lengths.length).toBeGreaterThan(2);
  for (const us of lengths.slice(1)) expect(Math.abs(us - (echo - missed))).toBeLessThan(10);
});

// fixtures/i2c.live.json: an LCD (0x27) and an OLED on the Uno's A4/A5, a DS1307 on D2/D3
test("I²C: the modules on A4/A5 are on the bus, powered by the circuit; one elsewhere is not", () => {
  const session = new Session(JSON.parse(fixture("i2c.live.json")));
  const board = session.attach("ARD_1", new Uno(fixture("i2c_lcd.hex")));
  const devices = modulesOn(session, board, {}, new Map());
  expect(devices.map((d) => d.address)).toEqual([0x27, 0x3c]);
  board.chip.i2c.devices = devices;
  session.advanceTo(1.5, 1e-3);
  expect((devices[0] as Backpack).screen().text[0].join("")).toBe("I2C works       ");
});

// runner.ts, as the worker runs it: the same circuits, the devices wired up by it
describe("Runner", () => {
  test("an HC-SR04 through the whole chain: its echo timed, the sketch's serial in the frames", () => {
    const runner = new Runner(JSON.parse(fixture("sonar.live.json")), [{ id: "US_1", kind: "ultrasonic", text: "100" }]);
    runner.attach("ARD_1", { board: "uno", hex: fixture("sonar.hex") });
    let serial = "";
    for (let t = 0.02; t <= 0.1; t += 0.02) {
      runner.advanceTo(t, 1e-3);
      serial += runner.frame().serial;
    }
    const lengths = serial.trim().split(/\s+/).map(Number).slice(1);
    expect(lengths.length).toBeGreaterThan(2);
    for (const us of lengths) expect(Math.abs(us - (5831 - 6.2 * 5))).toBeLessThan(10);
  });

  test("an I²C LCD shows its text, as dark as its trimmer is turned", () => {
    const parts = [{ id: "LCD_1", kind: "lcd1602_i2c", text: "0x27 70%" }];
    const runner = new Runner(JSON.parse(fixture("i2c.live.json")), parts);
    runner.attach("ARD_1", { board: "uno", hex: fixture("i2c_lcd.hex") });
    runner.advanceTo(1.5, 1e-3);
    const lit = runner.frame().screens.LCD_1;
    expect(lit.text[0].join("")).toBe("I2C works       ");
    expect([lit.contrast, lit.over]).toEqual([1, 0]);
    runner.setParts([{ id: "LCD_1", kind: "lcd1602_i2c", text: "0x27 20%" }]);
    expect(runner.frame().screens.LCD_1.contrast).toBeLessThan(0.3);
  });
});

// fixtures/pico.live.json: a Pico running blink.pico.ino, an LED on GP15, a potentiometer on GP26
test("a Pico in a circuit: its LED lights the circuit's, the potentiometer is its analogRead()", () => {
  const image = new Uint8Array(readFileSync(new URL("./fixtures/blink.pico.bin", import.meta.url)));
  const runner = new Runner(JSON.parse(fixture("pico.live.json")), [{ id: "P_1", kind: "potentiometer", text: "0.25" }]);
  runner.attach("PICO_1", { board: "pico", image });
  const seen = { lit: false, dark: false, board: new Set<number>() };
  let serial = "";
  for (let t = 0.01; t <= 0.6; t += 0.01) {
    runner.advanceTo(t, 1e-3);
    const f = runner.frame();
    serial += f.serial;
    const current = runner.session.sim.value("I_LED_1");
    if (current > 0.005) seen.lit = true;
    if (current < 1e-6) seen.dark = true;
    seen.board.add(f.looks.PICO_1?.led ?? -1);
  }
  expect(seen.lit && seen.dark).toBe(true); // (3.3 V − 2 V) / 260 Ω ≈ 5 mA when GP15 is high
  expect([...seen.board].sort()).toEqual([0, 1]); // the LED on the board, blinking with it
  // (the first reading is taken as analogRead() lets go of GP26's pull-down, which the circuit — a slice
  // behind the chip — still has: from the second on, the wiper's own voltage)
  const adc = [...serial.matchAll(/adc=(\d+)/g)].map((m) => Number(m[1])).slice(1);
  expect(adc.length).toBeGreaterThan(2);
  for (const a of adc) expect(Math.abs(a - 1023 * 0.75)).toBeLessThan(4); // the wiper a quarter from 3V3
});

// fixtures/sonar.live.json: the Uno's D9 wired to the sensor's TRIG, D2 to nothing
test("a pin wired to nothing toggling: no steps of the circuit for it, only its last state; a wired one steps it", () => {
  const uno = new Uno(fixture("sonar.hex"));
  const run = (pin: string) => {
    const session = new Session(JSON.parse(fixture("sonar.live.json")));
    let time = 0, level: Mode = "low", changes: PinChange[] = [];
    const chip: Chip = {
      pins: uno.pins, modes: uno.modes, i2c: uno.i2c, sda: uno.sda, scl: uno.scl, time: 0, onSerial: null,
      sense: () => {}, send: () => {},
      initial: () => uno.pins.map((p) => [p, p === pin ? level : "low"]),
      runUntil(t) { // (toggled every microsecond: a thousand changes a millisecond)
        for (let at = time + 1e-6; at <= t; at += 1e-6) changes.push({ time: at, pin, mode: (level = level === "low" ? "high" : "low") });
        time = t;
      },
      take() { const c = changes; changes = []; return c; },
    };
    session.attach("ARD_1", chip);
    let steps = 0;
    session.advanceTo(0.01, 1e-3, () => steps++);
    return { steps, driven: session.sim.p[session.sim.program.inputs[`ARD_1_${pin}_E`]], level };
  };
  const free = run("D2"), wired = run("D9");
  expect(free.steps).toBeLessThan(50); // (10 slices of 1 ms: a step or a few each)
  expect(free.driven).toBe(uno.modes[free.level][1]); // (as it was at the slice's end)
  expect(wired.steps).toBeGreaterThan(5000);
});
