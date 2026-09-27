import { SqlClient } from "@effect/sql"
import { slugify } from "@electro/notes-api"
import { Effect } from "effect"

/** Notes saved without a slug (by a server that had 0003 but not yet the code writing slugs) get one. */
export default Effect.gen(function* () {
  const sql = yield* SqlClient.SqlClient
  const taken = new Set(
    (yield* sql<{ slug: string }>`SELECT slug FROM notes WHERE slug IS NOT NULL UNION SELECT slug FROM note_slugs`)
      .map((r) => r.slug),
  )
  const rows = yield* sql<{ id: string; title: string }>`SELECT id, title FROM notes WHERE slug IS NULL ORDER BY saved_at`
  for (const row of rows) {
    const base = slugify(row.title)
    let slug = base
    for (let n = 2; taken.has(slug); n++) slug = `${base}-${n}`
    taken.add(slug)
    yield* sql`UPDATE notes SET slug = ${slug} WHERE id = ${row.id}`
  }
})
