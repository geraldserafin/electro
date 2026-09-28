import { describe, expect, it } from "vitest"
import { prepare } from "../src/Arduino.js"

describe("prepare", () => {
  it("declares every function above the first one, keeping the sketch's line numbers", () => {
    const sketch = [
      "// blink",            // 1
      "const int LED = 13;", // 2
      "",                    // 3
      "void setup() {",      // 4
      "  pinMode(LED, OUTPUT); // not a function {",
      "}",
      "void loop() { blink(200); }",
      "static int blink(unsigned long ms) {",
      '  if (ms) { Serial.print("}"); }',
      "  return 0;",
      "}",
    ].join("\n")
    const out = prepare(sketch)
    expect(out).toContain("void setup();\nvoid loop();\nstatic int blink(unsigned long ms);\n#line 4 \"sketch.ino\"\nvoid setup() {")
    expect(out.startsWith('#include <Arduino.h>\n#line 1 "sketch.ino"\n// blink\nconst int LED = 13;\n\n')).toBe(true)
  })

  it("leaves out what is not a function definition", () => {
    const out = prepare("struct P { int x; };\nint f(int a = 1) { return a; }\nvoid g() {}\n")
    expect(out).not.toContain("struct P;")
    expect(out).not.toContain("int f(int a = 1);")
    expect(out).toContain("void g();")
  })
})
