/**
 * Where everything lives: Postgres, schema kept by migrations. The rest of the server only sees
 * @effect/sql's SqlClient.
 */
import { NodeContext } from "@effect/platform-node"
import { PgClient, PgMigrator } from "@effect/sql-pg"
import { Config, Effect, Layer, Redacted } from "effect"
import users from "./migrations/0001_users.js"
import notes from "./migrations/0002_notes.js"
import library from "./migrations/0003_library.js"

/** Every migration, by name (a test of one starts the database from those before it: ``layer(url, record)``). */
export const migrations = { "0001_users": users, "0002_notes": notes, "0003_library": library }

const loaderOf = (record: Partial<typeof migrations>) => PgMigrator.fromRecord(record)

/** Postgres at `url`, migrated to the current schema. */
export const layer = (url: string, record: Partial<typeof migrations> = migrations) => {
  const client = PgClient.layer({ url: Redacted.make(url) })
  const migrated = PgMigrator.layer({ loader: loaderOf(record) }).pipe(Layer.provide([client, NodeContext.layer]))
  return Layer.merge(client, migrated)
}

/** The database at DATABASE_URL (by default devenv's: postgres://postgres:postgres@127.0.0.1:5192/electro). */
export const layerConfig = Layer.unwrapEffect(
  Effect.gen(function* () {
    const url = yield* Config.string("DATABASE_URL").pipe(Config.withDefault("postgres://postgres:postgres@127.0.0.1:5192/electro"))
    const { host, pathname } = new URL(url)
    yield* Effect.logInfo(`Baza: ${host}${pathname}`)
    return layer(url)
  }),
)
