/**
 * Notes in the database. Saving is optimistic: a client says which revision it started from,
 * and a save from an older one (someone saved in between) is a conflict, not an overwrite.
 */
import { SqlClient, SqlSchema } from "@effect/sql"
import {
  Note, NoteNotFound, NotePreview, NoteSummary, NotebookDocument, RevisionConflict, type NoteId, type Saved,
} from "@electro/notes-api"
import { DateTime, Effect, Option, Schema } from "effect"
import { preview } from "./preview.js"

const Row = Schema.Struct({
  id: Schema.String,
  title: Schema.String,
  document: Schema.String,
  revision: Schema.Int,
  modified: Schema.String,
  saved_at: Schema.String,
  cells: Schema.Int,
  schematics: Schema.Int,
  preview: Schema.parseJson(NotePreview),
})

const DocumentJson = Schema.parseJson(NotebookDocument)

export class NotesRepo extends Effect.Service<NotesRepo>()("NotesRepo", {
  effect: Effect.gen(function* () {
    const sql = yield* SqlClient.SqlClient

    const summaries = SqlSchema.findAll({
      Request: Schema.Void,
      Result: Row,
      execute: () => sql`SELECT * FROM notes ORDER BY saved_at DESC, id`,
    })
    const byId = SqlSchema.findOne({
      Request: Schema.String,
      Result: Row,
      execute: (id) => sql`SELECT * FROM notes WHERE id = ${id}`,
    })

    const list = summaries().pipe(
      Effect.map((rows) => rows.map((r): NoteSummary => ({
        id: r.id, title: r.title, modified: r.modified, savedAt: r.saved_at, revision: r.revision,
        cells: r.cells, schematics: r.schematics, preview: r.preview,
      }))),
      Effect.orDie, // a broken database is a server error, not something the client can act on
      Effect.withSpan("NotesRepo.list"),
    )

    const get = (id: NoteId) =>
      byId(id).pipe(
        Effect.orDie,
        Effect.flatMap(Option.match({
          onNone: () => Effect.fail(new NoteNotFound({ id })),
          onSome: (r) => Schema.decode(DocumentJson)(r.document).pipe(
            Effect.orDie,
            Effect.map((document): Note => ({ document, revision: r.revision, savedAt: r.saved_at })),
          ),
        })),
        Effect.withSpan("NotesRepo.get", { attributes: { id } }),
      )

    /** Create (baseRevision null) or update (baseRevision = the stored revision). */
    const save = (document: NotebookDocument, baseRevision: number | null) =>
      Effect.gen(function* () {
        const current = yield* byId(document.id).pipe(Effect.orDie)
        const stored = Option.map(current, (r) => r.revision)
        if (Option.isSome(stored) ? stored.value !== baseRevision : baseRevision !== null)
          return yield* Effect.fail(new RevisionConflict({
            id: document.id, current: Option.getOrElse(stored, () => 0), base: baseRevision,
          }))
        const revision = Option.getOrElse(stored, () => 0) + 1
        const savedAt = DateTime.formatIso(yield* DateTime.now)
        const json = yield* Schema.encode(DocumentJson)(document).pipe(Effect.orDie)
        const row = {
          id: document.id, title: document.title, document: json, revision, modified: document.modified,
          saved_at: savedAt, cells: document.cells.length,
          schematics: document.cells.filter((c) => c.type === "schematic").length,
          preview: JSON.stringify(preview(document)),
        }
        yield* (Option.isSome(stored)
          ? sql`UPDATE notes SET ${sql.update(row, ["id"])} WHERE id = ${document.id}`
          : sql`INSERT INTO notes ${sql.insert(row)}`
        ).pipe(Effect.orDie)
        return { revision, savedAt } satisfies Saved
      }).pipe(
        sql.withTransaction, // read-check-write as one step: two saves cannot both win
        Effect.catchTag("SqlError", Effect.die),
        Effect.withSpan("NotesRepo.save", { attributes: { id: document.id, baseRevision } }),
      )

    const remove = (id: NoteId) =>
      Effect.gen(function* () {
        const gone = yield* sql`DELETE FROM notes WHERE id = ${id} RETURNING id`.pipe(Effect.orDie)
        if (gone.length === 0) return yield* Effect.fail(new NoteNotFound({ id }))
      }).pipe(Effect.withSpan("NotesRepo.remove", { attributes: { id } }))

    return { list, get, save, remove } as const
  }),
}) {}
