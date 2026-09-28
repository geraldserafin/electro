/**
 * Where everything lives: Postgres, schema kept by migrations. The rest of the server only sees
 * @effect/sql's SqlClient.
 */
import { NodeContext } from "@effect/platform-node"
import { PgClient, PgMigrator } from "@effect/sql-pg"
import { Config, Effect, Layer, Redacted } from "effect"
import users from "./migrations/0001_users.js"
import notes from "./migrations/0002_notes.js"

const migrations = PgMigrator.fromRecord({ "0001_users": users, "0002_notes": notes })

/** Postgres at `url`, migrated to the current schema. */
export const layer = (url: string) => {
  const client = PgClient.layer({ url: Redacted.make(url) })
  const migrated = PgMigrator.layer({ loader: migrations }).pipe(Layer.provide([client, NodeContext.layer]))
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
