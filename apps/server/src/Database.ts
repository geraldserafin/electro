/**
 * Where notes live: SQLite (a file; ":memory:" in tests), schema kept by migrations. The rest
 * of the server only sees @effect/sql's SqlClient, so moving to Postgres is this file.
 */
import { NodeContext } from "@effect/platform-node"
import { SqliteClient, SqliteMigrator } from "@effect/sql-sqlite-node"
import { Config, Effect, Layer } from "effect"
import { mkdirSync } from "node:fs"
import { dirname } from "node:path"
import notes from "./migrations/0001_notes.js"
import preview from "./migrations/0002_preview.js"

const migrations = SqliteMigrator.fromRecord({ "0001_notes": notes, "0002_preview": preview })

/** SQLite at `filename`, migrated to the current schema. */
export const layer = (filename: string) => {
  const client = SqliteClient.layer({ filename })
  const migrated = SqliteMigrator.layer({ loader: migrations }).pipe(Layer.provide([client, NodeContext.layer]))
  return Layer.merge(client, migrated)
}

/** The database file from DATABASE_PATH (default .data/notes.sqlite, created if missing). */
export const layerConfig = Layer.unwrapEffect(
  Effect.gen(function* () {
    const filename = yield* Config.string("DATABASE_PATH").pipe(Config.withDefault(".data/notes.sqlite"))
    if (filename !== ":memory:") mkdirSync(dirname(filename), { recursive: true })
    yield* Effect.logInfo(`Baza notatek: ${filename}`)
    return layer(filename)
  }),
)
