// The I²C devices against real sketches using their usual libraries (fixtures/i2c_lcd.ino,
// oled.ino, rtc.ino): the emulated Uno's TWI talking to them over the bus in the page.
import { readFileSync } from "node:fs";
import { describe, expect, test } from "vitest";
import { Uno } from "./arduino";
import { Backpack, Clock, Oled } from "./i2c";

const hex = (name: string) => readFileSync(new URL(`./fixtures/${name}.hex`, import.meta.url), "utf8");
const on = () => true;

describe("a 16×2 LCD behind a PCF8574 (LiquidCrystal_I2C)", () => {
  const uno = new Uno(hex("i2c_lcd"));
  const lcd = new Backpack("LCD_1", 0x27, on);
  uno.i2c.devices.push(lcd);
  uno.runUntil(1.5); // init() waits a second for the LCD to power up

  test("shows what was printed, lit", () => {
    const s = lcd.screen();
    expect(s.text.map((line) => line.join(""))).toEqual(["I2C works       ", "42              "]);
    expect(s.backlight).toBe(1);
    expect(s.contrast).toBe(1);
  });

  test("at another address nobody answers: nothing shown", () => {
    const other = new Uno(hex("i2c_lcd"));
    const away = new Backpack("LCD_2", 0x3f, on);
    other.i2c.devices.push(away);
    other.runUntil(1.5);
    expect(away.screen().contrast).toBe(0);
  });
});

describe("a 128×64 SSD1306 (Adafruit_SSD1306)", () => {
  const uno = new Uno(hex("oled"));
  const oled = new Oled("OLED_1", 0x3c, on);
  uno.i2c.devices.push(oled);
  uno.runUntil(0.5);
  const { rows, on: shown } = oled.pixels();

  test("is on, with a pixel in each corner — the right way up", () => {
    expect(shown).toBe(true);
    expect([rows[0][0], rows[0][127], rows[63][0], rows[63][127]]).toEqual([1, 1, 1, 1]);
    expect(rows[0][1]).toBe(0);
  });

  test("and the box where it was drawn", () => {
    expect(rows[20][10] && rows[27][39]).toBe(1);
    expect(rows[19][10] || rows[28][10] || rows[20][9] || rows[20][40]).toBe(0);
    expect(rows.reduce((n, r) => n + r.reduce((m, p) => m + p, 0), 0)).toBe(4 + 30 * 8);
  });
});

describe("a DS1307 (RTClib)", () => {
  test("keeps the time it was set to, running with the circuit", () => {
    const uno = new Uno(hex("rtc"));
    uno.i2c.devices.push(new Clock("RTC_1", 0x68, on, () => uno.time));
    let serial = "";
    uno.onSerial = (c) => (serial += c);
    uno.runUntil(2.2);
    expect(serial.trim()).toMatch(/^2024-5-17 13:45:3[12]$/);
  });
});
