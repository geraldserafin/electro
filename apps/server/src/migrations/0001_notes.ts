import { SqlClient } from "@effect/sql"
import { Effect } from "effect"

/**
 * One table of notes. The document is stored whole (JSON); title and counts are copied out so
 * a list needs no parsing. No user yet: per-user notes add a user_id column (and key) later.
 */
export default Effect.gen(function* () {
  const sql = yield* SqlClient.SqlClient
  yield* sql`
    CREATE TABLE notes (
      id          TEXT PRIMARY KEY,
      title       TEXT NOT NULL,
      document    TEXT NOT NULL,
      revision    INTEGER NOT NULL,
      modified    TEXT NOT NULL,
      saved_at    TEXT NOT NULL,
      cells       INTEGER NOT NULL,
      schematics  INTEGER NOT NULL
    )
  `
  yield* sql`CREATE INDEX notes_by_saved_at ON notes (saved_at DESC)`
})
