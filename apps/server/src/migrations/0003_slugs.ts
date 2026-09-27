import { SqlClient } from "@effect/sql"
import { slugify } from "@electro/notes-api"
import { Effect } from "effect"

/**
 * Addresses from titles: each note gets a unique slug; slugs it had before stay in note_slugs,
 * so old links keep finding it. The notes saved before get theirs here.
 */
export default Effect.gen(function* () {
  const sql = yield* SqlClient.SqlClient
  yield* sql`ALTER TABLE notes ADD COLUMN slug TEXT`
  yield* sql`
    CREATE TABLE note_slugs (
      slug     TEXT PRIMARY KEY,
      note_id  TEXT NOT NULL
    )
  `
  const rows = yield* sql<{ id: string; title: string }>`SELECT id, title FROM notes ORDER BY saved_at`
  const taken = new Set<string>()
  for (const row of rows) {
    const base = slugify(row.title)
    let slug = base
    for (let n = 2; taken.has(slug); n++) slug = `${base}-${n}`
    taken.add(slug)
    yield* sql`UPDATE notes SET slug = ${slug} WHERE id = ${row.id}`
  }
  yield* sql`CREATE UNIQUE INDEX notes_by_slug ON notes (slug)`
})
