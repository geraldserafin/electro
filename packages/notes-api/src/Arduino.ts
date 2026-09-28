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
