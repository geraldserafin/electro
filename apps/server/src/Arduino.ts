/** Sketches compiled with arduino-cli (board arduino:avr:uno), one at a time, each in a directory of
 *  its own that is removed afterwards; the same sketch twice is compiled once (kept in memory).
 *
 *  The sketch goes in as C++ (prepared here, like the Arduino IDE would), so arduino-cli's own
 *  preprocessing — ctags, which differs from build to build — has nothing to do. */
import { HttpApiBuilder } from "@effect/platform"
import { CompileFailed, CompilerUnavailable, NotesApi } from "@electro/notes-api"
import { Config, Effect } from "effect"
import { execFile } from "node:child_process"
import { createHash } from "node:crypto"
import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"

const FQBN = "arduino:avr:uno"
const TIMEOUT_MS = 90_000
const CACHE_SIZE = 200

type Outcome = { hex: string } | { failed: string } | { unavailable: true }

/** What the Arduino IDE does to a sketch: ``#include <Arduino.h>`` on top, and a prototype of each
 *  function before the first one, so a function may be called above its definition. ``#line``
 *  keeps the compiler's line numbers the sketch's own. */
export function prepare(sketch: string): string {
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
  return `#include <Arduino.h>\n#line 1 "sketch.ino"\n${sketch.slice(0, at)}${prototypes.map((p) => `${p}\n`).join("")}` +
    `#line ${line} "sketch.ino"\n${sketch.slice(at)}`
}

function compile(cli: string, properties: string[], sketch: string): Promise<Outcome> {
  return (async () => {
    const dir = await mkdtemp(join(tmpdir(), "electro-sketch-"))
    try {
      const src = join(dir, "sketch")
      await mkdir(src)
      await writeFile(join(src, "sketch.ino"), "") // the sketch itself is the C++ file next to it
      await writeFile(join(src, "sketch_code.cpp"), prepare(sketch))
      const out = join(dir, "out")
      return await new Promise<Outcome>((resolve) => {
        const args = ["compile", "--fqbn", FQBN, "--output-dir", out, ...properties.flatMap((p) => ["--build-property", p]), src]
        execFile(cli, args, { timeout: TIMEOUT_MS, maxBuffer: 4 << 20 },
          (error, stdout, stderr) => {
            if (error && (error as NodeJS.ErrnoException).code === "ENOENT") return resolve({ unavailable: true })
            if (error) {
              // the paths of this temporary directory mean nothing to the reader: sketch.ino:12:3 is enough
              const text = `${stderr}${stdout}`.replaceAll(`${src}/`, "").replaceAll(dir, "").replace(/\x1b\[[0-9;]*m/g, "")
                .split("\nError during build")[0] // then only arduino-cli's summary
              return resolve(text.includes("platform not installed") || text.includes("Platform 'arduino:avr' not found")
                ? { unavailable: true } : { failed: text.trim() })
            }
            readFile(join(out, "sketch.ino.hex"), "utf8").then((hex) => resolve({ hex }), () => resolve({ unavailable: true }))
          })
      })
    } finally {
      await rm(dir, { recursive: true, force: true })
    }
  })()
}

export const ArduinoLive = HttpApiBuilder.group(NotesApi, "arduino", (handlers) =>
  Effect.gen(function* () {
    const cli = yield* Config.string("ARDUINO_CLI").pipe(Config.withDefault("arduino-cli"))
    // a compiler and ctags other than the core's own (devenv.nix: on an ARM Mac)
    const compilerPath = yield* Config.string("ARDUINO_COMPILER_PATH").pipe(Config.withDefault(""))
    const ctagsPath = yield* Config.string("ARDUINO_CTAGS_PATH").pipe(Config.withDefault(""))
    const properties = [
      ...(compilerPath ? [`compiler.path=${compilerPath}`] : []),
      ...(ctagsPath ? [`tools.ctags.path=${ctagsPath}`] : []),
    ]
    const one = yield* Effect.makeSemaphore(1)
    const cache = new Map<string, string>()
    return handlers.handle("compile", ({ payload }) =>
      Effect.gen(function* () {
        const key = createHash("sha256").update(payload.sketch).digest("hex")
        const kept = cache.get(key)
        if (kept !== undefined) return { hex: kept }
        const outcome = yield* one.withPermits(1)(Effect.promise(() => compile(cli, properties, payload.sketch)))
        if ("unavailable" in outcome) return yield* Effect.fail(new CompilerUnavailable())
        if ("failed" in outcome) return yield* Effect.fail(new CompileFailed({ output: outcome.failed }))
        if (cache.size >= CACHE_SIZE) cache.delete(cache.keys().next().value!)
        cache.set(key, outcome.hex)
        return { hex: outcome.hex }
      }))
  }))
