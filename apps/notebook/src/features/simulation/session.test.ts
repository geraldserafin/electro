// A circuit, a chip and a device in the page together (session.ts): an HC-SR04 on an Uno running
// fixtures/sonar.ino (pulseIn() on its echo). The circuit is fixtures/sonar.live.json
// (scripts/make_sim_fixtures.py); the sensor's timing is peripherals.ts's, scheduled as useLive does.
import { readFileSync } from "node:fs";
import { expect, test } from "vitest";
import { Backpack, modulesOn } from "./i2c";
import { ping, sonar } from "./peripherals";
import { Session } from "./session";

const fixture = (name: string) => readFileSync(new URL(`./fixtures/${name}`, import.meta.url), "utf8");

function measure(distance: number) {
  const session = new Session(JSON.parse(fixture("sonar.live.json")));
  const board = session.attach("ARD_1", fixture("sonar.hex"));
  let serial = "";
  board.uno.onSerial = (c) => (serial += c);
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
  const board = session.attach("ARD_1", fixture("i2c_lcd.hex"));
  const devices = modulesOn(session, board, {}, new Map());
  expect(devices.map((d) => d.address)).toEqual([0x27, 0x3c]);
  board.uno.i2c.devices = devices;
  session.advanceTo(1.5, 1e-3);
  expect((devices[0] as Backpack).screen().text[0].join("")).toBe("I2C works       ");
});
