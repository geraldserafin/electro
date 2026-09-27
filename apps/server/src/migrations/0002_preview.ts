import { SqlClient } from "@effect/sql"
import { NotebookDocument, previewOf } from "@electro/notes-api"
import { Effect, Schema } from "effect"

/** A thumbnail of each note's first page, kept next to it; made for the notes saved before. */
export default Effect.gen(function* () {
  const sql = yield* SqlClient.SqlClient
  yield* sql`ALTER TABLE notes ADD COLUMN preview TEXT NOT NULL DEFAULT '{"codeInPdf":true,"cells":[]}'`
  const rows = yield* sql<{ id: string; document: string }>`SELECT id, document FROM notes`
  for (const row of rows) {
    const document = yield* Schema.decode(Schema.parseJson(NotebookDocument))(row.document)
    yield* sql`UPDATE notes SET preview = ${JSON.stringify(previewOf(document))} WHERE id = ${row.id}`
  }
})
