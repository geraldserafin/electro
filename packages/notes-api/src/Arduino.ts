/** Compiling an Arduino sketch for the notebook's live simulation: C++ in, the machine code (Intel
 *  HEX, for an ATmega328P) out; the page runs it in an emulated chip. Signed-in users only: the
 *  compiler runs on the server. */
import { HttpApiEndpoint, HttpApiGroup, HttpApiSchema } from "@effect/platform"
import { Schema } from "effect"
import { Authentication } from "./Auth.js"

export const Sketch = Schema.Struct({ sketch: Schema.String.pipe(Schema.maxLength(65536)) })

export const Compiled = Schema.Struct({ hex: Schema.String })

/** The compiler said no: its output (errors with line numbers) as it wrote it. */
export class CompileFailed extends Schema.TaggedError<CompileFailed>()(
  "CompileFailed",
  { output: Schema.String },
  HttpApiSchema.annotations({ status: 422 }),
) {
  get message() {
    return `The sketch does not compile:\n${this.output}`
  }
}

/** The server has no Arduino compiler (arduino-cli with the arduino:avr core). */
export class CompilerUnavailable extends Schema.TaggedError<CompilerUnavailable>()(
  "CompilerUnavailable",
  {},
  HttpApiSchema.annotations({ status: 503 }),
) {
  get message() {
    return "No Arduino compiler on the server."
  }
}

// A global object with a destructor (Adafruit_SSD1306 display(...)) has it registered with
// __cxa_atexit; Arduino's own avr-gcc is built without it, other compilers (nixpkgs' avr-gcc, clang)
// want it linked in. A sketch never ends, so the destructors never run: weak, doing nothing.
const RUNTIME = 'extern "C" __attribute__((weak)) int __cxa_atexit(void (*)(void *), void *, void *) { return 0; }\n' +
  "__attribute__((weak)) void *__dso_handle;\n"

/** What the Arduino IDE does to a sketch: ``#include <Arduino.h>`` on top, and a prototype of each
 *  function before the first one, so a function may be called above its definition. ``#line``
 *  keeps the compiler's line numbers the sketch's own. (And RUNTIME.) */
export function prepareSketch(sketch: string): string {
  const blank = (m: string) => m.replace(/[^\n]/g, " ")
  // what to look at: no comments, strings or preprocessor lines (same length, same lines)
  const code = sketch
    .replace(/\/\*[\s\S]*?\*\/|\/\/[^\n]*|"(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*'/g, blank)
    .replace(/^[ \t]*#[^\n]*/gm, blank)
  const prototypes: string[] = []
  let first = -1, depth = 0, start = 0
  for (let i = 0; i < code.length; i++) {
    const c = code[i]
    if (c === "{") {
      if (depth === 0) {
        const head = code.slice(start, i).replace(/\s+/g, " ").trim()
        const m = head.match(/^((?:[A-Za-z_][\w:<>,]*[\s*&]+)+)([A-Za-z_]\w*)\s*\(([^()]*)\)(\s*const)?$/)
        if (m && !/\b(struct|class|enum|union|namespace|typedef|if|while|for|switch|return)\b/.test(m[1]) && !m[3].includes("=")) {
          prototypes.push(`${m[1].trim()} ${m[2]}(${m[3].trim()});`)
          if (first < 0) first = start + code.slice(start, i).search(/\S/)
        }
      }
      depth++
    } else if (c === "}") {
      depth--
      if (depth === 0) start = i + 1
    } else if (c === ";" && depth === 0) start = i + 1
  }
  // the prototypes go on their own lines, just above the line the first function starts on
  const at = first < 0 ? sketch.length : sketch.lastIndexOf("\n", first - 1) + 1
  const line = sketch.slice(0, at).split("\n").length
  return `#include <Arduino.h>\n${RUNTIME}#line 1 "sketch.ino"\n${sketch.slice(0, at)}${prototypes.map((p) => `${p}\n`).join("")}` +
    `#line ${line} "sketch.ino"\n${sketch.slice(at)}`
}

export class ArduinoGroup extends HttpApiGroup.make("arduino")
  .add(
    HttpApiEndpoint.post("compile", "/arduino/compile")
      .setPayload(Sketch)
      .addSuccess(Compiled)
      .addError(CompileFailed)
      .addError(CompilerUnavailable),
  )
  .middleware(Authentication)
{}
