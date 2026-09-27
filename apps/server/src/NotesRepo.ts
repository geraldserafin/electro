/**
 * Notes in the database. Saving is optimistic: a client says which revision it started from,
 * and a save from an older one (someone saved in between) is a conflict, not an overwrite.
 * Each note has an address made from its title (a unique slug); the slugs it had before keep
 * leading to it.
 */
import { SqlClient, SqlSchema } from "@effect/sql"
import {
  Note, NoteNotFound, NotePreview, NoteSummary, NotebookDocument, previewOf, RevisionConflict, slugify,
  type NoteId, type Saved,
} from "@electro/notes-api"
import { DateTime, Effect, Option, Schema } from "effect"

const Row = Schema.Struct({
  id: Schema.String,
  slug: Schema.String,
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
    /** By address: the id, the current slug, or one it had before. */
    const byRef = SqlSchema.findOne({
      Request: Schema.String,
      Result: Row,
      execute: (ref) => sql`
        SELECT * FROM notes WHERE id = ${ref} OR slug = ${ref}
        UNION ALL
        SELECT notes.* FROM note_slugs JOIN notes ON notes.id = note_slugs.note_id WHERE note_slugs.slug = ${ref}
        LIMIT 1
      `,
    })

    /** Taken by another note (as its slug now, or one it had)? */
    const takenByOther = (slug: string, id: string) =>
      sql<{ n: number }>`
        SELECT count(*) AS n FROM (
          SELECT id FROM notes WHERE slug = ${slug} AND id <> ${id}
          UNION ALL
          SELECT note_id FROM note_slugs WHERE slug = ${slug} AND note_id <> ${id}
        )
      `.pipe(Effect.map(([row]) => (row?.n ?? 0) > 0))

    /** The slug for `title`: kept while the title still makes it; else the first free one. */
    const slugFor = (id: string, title: string, current: string | null) =>
      Effect.gen(function* () {
        const base = slugify(title)
        if (current !== null && (current === base || new RegExp(`^${base}-\\d+$`).test(current))) return current
        let slug = base
        for (let n = 2; yield* takenByOther(slug, id); n++) slug = `${base}-${n}`
        return slug
      })

    const list = summaries().pipe(
      Effect.map((rows) => rows.map((r): NoteSummary => ({
        id: r.id, slug: r.slug, title: r.title, modified: r.modified, savedAt: r.saved_at, revision: r.revision,
        cells: r.cells, schematics: r.schematics, preview: r.preview,
      }))),
      Effect.orDie, // a broken database is a server error, not something the client can act on
      Effect.withSpan("NotesRepo.list"),
    )

    const get = (ref: string) =>
      byRef(ref).pipe(
        Effect.orDie,
        Effect.flatMap(Option.match({
          onNone: () => Effect.fail(new NoteNotFound({ id: ref })),
          onSome: (r) => Schema.decode(DocumentJson)(r.document).pipe(
            Effect.orDie,
            Effect.map((document): Note => ({ document, slug: r.slug, revision: r.revision, savedAt: r.saved_at })),
          ),
        })),
        Effect.withSpan("NotesRepo.get", { attributes: { ref } }),
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
        const before = Option.getOrNull(Option.map(current, (r) => r.slug))
        const slug = yield* slugFor(document.id, document.title, before).pipe(Effect.orDie)
        const row = {
          id: document.id, slug, title: document.title, document: json, revision, modified: document.modified,
          saved_at: savedAt, cells: document.cells.length,
          schematics: document.cells.filter((c) => c.type === "schematic").length,
          preview: JSON.stringify(previewOf(document)),
        }
        yield* (Option.isSome(stored)
          ? sql`UPDATE notes SET ${sql.update(row, ["id"])} WHERE id = ${document.id}`
          : sql`INSERT INTO notes ${sql.insert(row)}`
        ).pipe(Effect.orDie)
        if (before !== null && before !== slug) // the old address keeps leading here
          yield* sql`INSERT OR REPLACE INTO note_slugs (slug, note_id) VALUES (${before}, ${document.id})`.pipe(Effect.orDie)
        yield* sql`DELETE FROM note_slugs WHERE slug = ${slug}`.pipe(Effect.orDie) // now its current one
        return { revision, savedAt, slug } satisfies Saved
      }).pipe(
        sql.withTransaction, // read-check-write as one step: two saves cannot both win
        Effect.catchTag("SqlError", Effect.die),
        Effect.withSpan("NotesRepo.save", { attributes: { id: document.id, baseRevision } }),
      )

    const remove = (id: NoteId) =>
      Effect.gen(function* () {
        const gone = yield* sql`DELETE FROM notes WHERE id = ${id} RETURNING id`.pipe(Effect.orDie)
        if (gone.length === 0) return yield* Effect.fail(new NoteNotFound({ id }))
        yield* sql`DELETE FROM note_slugs WHERE note_id = ${id}`.pipe(Effect.orDie) // its old addresses are free again
      }).pipe(
        sql.withTransaction,
        Effect.catchTag("SqlError", Effect.die),
        Effect.withSpan("NotesRepo.remove", { attributes: { id } }),
      )

    return { list, get, save, remove } as const
  }),
}) {}
