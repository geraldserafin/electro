/** Sketches compiled with arduino-cli (board arduino:avr:uno), one at a time, each in a directory of
 *  its own that is removed afterwards; the same sketch twice is compiled once (kept in memory).
 *
 *  The sketch goes in as C++ (prepareSketch, @electro/notes-api: as the Arduino IDE would), so arduino-cli's own
 *  preprocessing — ctags, which differs from build to build — has nothing to do. */
import { HttpApiBuilder } from "@effect/platform"
import { CompileFailed, CompilerUnavailable, NotesApi, prepareSketch } from "@electro/notes-api"
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


function compile(cli: string, properties: string[], sketch: string): Promise<Outcome> {
  return (async () => {
    const dir = await mkdtemp(join(tmpdir(), "electro-sketch-"))
    try {
      const src = join(dir, "sketch")
      await mkdir(src)
      await writeFile(join(src, "sketch.ino"), "") // the sketch itself is the C++ file next to it
      await writeFile(join(src, "sketch_code.cpp"), prepareSketch(sketch))
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
