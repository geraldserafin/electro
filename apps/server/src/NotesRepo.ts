/**
 * Notes in the database, each user's apart: every query is by owner, so another user's note is
 * simply not there. Saving is optimistic: a client says which revision it started from, and a
 * save from an older one (someone saved in between) is a conflict, not an overwrite. Each note
 * has an address made from its title (a slug, unique per owner); the slugs it had before keep
 * leading to it.
 */
import { SqlClient, SqlSchema } from "@effect/sql"
import {
  Note, NoteNotFound, NotePreview, NoteSummary, NotebookDocument, previewOf, RevisionConflict, slugify,
  type NoteId, type Saved, type UserId,
} from "@electro/notes-api"
import { DateTime, Effect, Option, Schema } from "effect"

const Row = Schema.Struct({
  id: Schema.String,
  slug: Schema.String,
  title: Schema.String,
  document: Schema.Unknown, // jsonb: parsed already
  revision: Schema.Int,
  modified: Schema.String,
  saved_at: Schema.DateFromSelf,
  cells: Schema.Int,
  schematics: Schema.Int,
  preview: NotePreview,
})

const Key = Schema.Struct({ owner: Schema.String, ref: Schema.String })

export class NotesRepo extends Effect.Service<NotesRepo>()("NotesRepo", {
  effect: Effect.gen(function* () {
    const sql = yield* SqlClient.SqlClient

    const summaries = SqlSchema.findAll({
      Request: Schema.String,
      Result: Row,
      execute: (owner) => sql`SELECT * FROM notes WHERE owner_id = ${owner} ORDER BY saved_at DESC, id`,
    })
    const byId = SqlSchema.findOne({
      Request: Key,
      Result: Row,
      execute: ({ owner, ref }) => sql`SELECT * FROM notes WHERE owner_id = ${owner} AND id = ${ref}`,
    })
    /** By address: the id, the current slug, or one it had before. */
    const byRef = SqlSchema.findOne({
      Request: Key,
      Result: Row,
      execute: ({ owner, ref }) => sql`
        SELECT * FROM notes WHERE owner_id = ${owner} AND (id = ${ref} OR slug = ${ref})
        UNION ALL
        SELECT notes.* FROM note_slugs JOIN notes ON notes.owner_id = note_slugs.owner_id AND notes.id = note_slugs.note_id
        WHERE note_slugs.owner_id = ${owner} AND note_slugs.slug = ${ref}
        LIMIT 1
      `,
    })

    /** Taken by another of the owner's notes (as its slug now, or one it had)? */
    const takenByOther = (owner: UserId, slug: string, id: string) =>
      sql<{ taken: boolean }>`
        SELECT EXISTS (
          SELECT 1 FROM notes WHERE owner_id = ${owner} AND slug = ${slug} AND id <> ${id}
          UNION ALL
          SELECT 1 FROM note_slugs WHERE owner_id = ${owner} AND slug = ${slug} AND note_id <> ${id}
        ) AS taken
      `.pipe(Effect.map(([row]) => row?.taken ?? false))

    /** The slug for `title`: kept while the title still makes it; else the first free one. */
    const slugFor = (owner: UserId, id: string, title: string, current: string | null) =>
      Effect.gen(function* () {
        const base = slugify(title)
        if (current !== null && (current === base || new RegExp(`^${base}-\\d+$`).test(current))) return current
        let slug = base
        for (let n = 2; yield* takenByOther(owner, slug, id); n++) slug = `${base}-${n}`
        return slug
      })

    const list = (owner: UserId) =>
      summaries(owner).pipe(
        Effect.map((rows) => rows.map((r): NoteSummary => ({
          id: r.id, slug: r.slug, title: r.title, modified: r.modified, savedAt: r.saved_at.toISOString(),
          revision: r.revision, cells: r.cells, schematics: r.schematics, preview: r.preview,
        }))),
        Effect.orDie, // a broken database is a server error, not something the client can act on
        Effect.withSpan("NotesRepo.list"),
      )

    const get = (owner: UserId, ref: string) =>
      byRef({ owner, ref }).pipe(
        Effect.orDie,
        Effect.flatMap(Option.match({
          onNone: () => Effect.fail(new NoteNotFound({ id: ref })),
          onSome: (r) => Schema.decodeUnknown(NotebookDocument)(r.document).pipe(
            Effect.orDie,
            Effect.map((document): Note => ({ document, slug: r.slug, revision: r.revision, savedAt: r.saved_at.toISOString() })),
          ),
        })),
        Effect.withSpan("NotesRepo.get", { attributes: { ref } }),
      )

    /** Create (baseRevision null) or update (baseRevision = the stored revision). */
    const save = (owner: UserId, document: NotebookDocument, baseRevision: number | null) =>
      Effect.gen(function* () {
        // one save of an owner's at a time: read-check-write (the revision, a free slug) as one step
        yield* sql`SELECT pg_advisory_xact_lock(hashtextextended(${owner}, 0))`
        const current = yield* byId({ owner, ref: document.id })
        const stored = Option.map(current, (r) => r.revision)
        if (Option.isSome(stored) ? stored.value !== baseRevision : baseRevision !== null)
          return yield* Effect.fail(new RevisionConflict({
            id: document.id, current: Option.getOrElse(stored, () => 0), base: baseRevision,
          }))
        const revision = Option.getOrElse(stored, () => 0) + 1
        const savedAt = DateTime.formatIso(yield* DateTime.now)
        const json = yield* Schema.encode(Schema.parseJson(NotebookDocument))(document).pipe(Effect.orDie)
        const before = Option.getOrNull(Option.map(current, (r) => r.slug))
        const slug = yield* slugFor(owner, document.id, document.title, before)
        const row = {
          owner_id: owner, id: document.id, slug, title: document.title, document: json, revision,
          modified: document.modified, saved_at: savedAt, cells: document.cells.length,
          schematics: document.cells.filter((c) => c.type === "schematic").length,
          preview: JSON.stringify(previewOf(document)),
        }
        yield* Option.isSome(stored)
          ? sql`UPDATE notes SET ${sql.update(row, ["owner_id", "id"])} WHERE owner_id = ${owner} AND id = ${document.id}`
          : sql`INSERT INTO notes ${sql.insert(row)}`
        if (before !== null && before !== slug) // the old address keeps leading here
          yield* sql`INSERT INTO note_slugs (owner_id, slug, note_id) VALUES (${owner}, ${before}, ${document.id})
                     ON CONFLICT (owner_id, slug) DO UPDATE SET note_id = excluded.note_id`
        yield* sql`DELETE FROM note_slugs WHERE owner_id = ${owner} AND slug = ${slug}` // now its current one
        return { revision, savedAt, slug } satisfies Saved
      }).pipe(
        sql.withTransaction,
        Effect.catchTags({ SqlError: Effect.die, ParseError: Effect.die }),
        Effect.withSpan("NotesRepo.save", { attributes: { id: document.id, baseRevision } }),
      )

    /** Its old addresses go with it (and are free again). */
    const remove = (owner: UserId, id: NoteId) =>
      sql`DELETE FROM notes WHERE owner_id = ${owner} AND id = ${id} RETURNING id`.pipe(
        Effect.orDie,
        Effect.flatMap((gone) => gone.length === 0 ? Effect.fail(new NoteNotFound({ id })) : Effect.void),
        Effect.withSpan("NotesRepo.remove", { attributes: { id } }),
      )

    return { list, get, save, remove } as const
  }),
}) {}
