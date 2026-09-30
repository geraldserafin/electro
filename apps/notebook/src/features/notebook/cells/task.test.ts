import { describe, expect, it } from "vitest";
import { isRight, parseAnswer } from "./task";

// from electro.task: task(supply(12) + Resistor(10) + Resistor(20) + ground, "I_R_1") — the answer is 0.4 A
const HASHES = [
  "196481a0f2d0c26263c959a76b76283e0238276ee8179268dfe5db9b8a4e8232",
  "2595c48ca7b5c7b09e7a53887d2be88264bd3336ee28e2d2868dda13e96a20d1",
  "31fbe96b9b012af6cdf6231457223f35ae931759a15433b1f6f8d19745d62b30",
];

describe("task", () => {
  it("reads answers as people type them", () => {
    expect(parseAnswer("0,4")).toBe(0.4);
    expect(parseAnswer("400m")).toBeCloseTo(0.4);
    expect(parseAnswer("400 mA")).toBeCloseTo(0.4);
    expect(parseAnswer("-2.5e-3 V")).toBe(-0.0025);
    expect(parseAnswer("abc")).toBeNull();
  });

  it("checks against the hashes Python made, within 1 %", async () => {
    expect(await isRight("I_R_1", 0.4, 0.01, HASHES)).toBe(true);
    expect(await isRight("I_R_1", 0.402, 0.01, HASHES)).toBe(true);
    expect(await isRight("I_R_1", 0.41, 0.01, HASHES)).toBe(false);
    expect(await isRight("I_R_2", 0.4, 0.01, HASHES)).toBe(false); // another quantity, another hash
  });
});
