/**
 * The library in the database: folders and notes, and who may see them. Every call starts from
 * the user: what they may do with an item is the best of owning it and the shares of it or of a
 * folder above it (roleIn); an item they may not see is simply not there (NotFound).
 *
 * Saving a note is optimistic: a client says which revision it started from, and a save from an
 * older one is a conflict, not an overwrite. Deleting an item, or moving it out of its folder,
 * takes its owner or an editor of that folder — not someone it was shared with on its own.
 */
import { SqlClient, SqlSchema } from "@effect/sql"
import {
  MoveIntoItself, NotAFolder, NotebookDocument, NotFound, NotePreview, OtherOwner, previewOf, RANK,
  RevisionConflict, Role, RoleTooLow,
  type Crumb, type Destination, type Folder, type ItemCard, type Note, type Saved, type UserId,
} from "@electro/notes-api"
import { DateTime, Effect, Schema } from "effect"
import { randomUUID } from "node:crypto"

const CardRow = Schema.Struct({
  id: Schema.String,
  kind: Schema.Literal("folder", "note"),
  name: Schema.String,
  parent_id: Schema.NullOr(Schema.String),
  owner_id: Schema.String,
  owner_name: Schema.String,
  owner_avatar: Schema.NullOr(Schema.String),
  modified: Schema.NullOr(Schema.String),
  saved_at: Schema.DateFromSelf,
  preview: Schema.NullOr(NotePreview),
  previews: Schema.Array(NotePreview),
  count: Schema.Int,
  shared_role: Schema.NullOr(Schema.Literal("editor", "viewer")), // a share of this very item with the user
})
type CardRow = typeof CardRow.Type

/** An item and the folders above it: the start of every check. */
const UpRow = Schema.Struct({
  id: Schema.String,
  parent_id: Schema.NullOr(Schema.String),
  owner_id: Schema.String,
  kind: Schema.Literal("folder", "note"),
  name: Schema.String,
  depth: Schema.Int,
  shared_role: Schema.NullOr(Schema.Literal("editor", "viewer")),
})
type UpRow = typeof UpRow.Type

const better = (a: Role | null, b: Role | null): Role | null =>
  a === null ? b : b === null ? a : RANK[a] >= RANK[b] ? a : b

const newId = () => randomUUID().replaceAll("-", "")

export class LibraryRepo extends Effect.Service<LibraryRepo>()("LibraryRepo", {
  effect: Effect.gen(function* () {
    const sql = yield* SqlClient.SqlClient

    /** The item and every folder above it (depth 0: the item), each with its share for the user. */
    const upFrom = SqlSchema.findAll({
      Request: Schema.Struct({ user: Schema.String, id: Schema.String }),
      Result: UpRow,
      execute: ({ user, id }) => sql`
        WITH RECURSIVE up(id, parent_id, owner_id, kind, name, depth) AS (
          SELECT id, parent_id, owner_id, kind, name, 0 FROM items WHERE id = ${id}
          UNION ALL
          SELECT i.id, i.parent_id, i.owner_id, i.kind, i.name, up.depth + 1 FROM items i JOIN up ON i.id = up.parent_id
        )
        SELECT up.*, s.role AS shared_role FROM up
        LEFT JOIN shares s ON s.item_id = up.id AND s.user_id = ${user}
        ORDER BY up.depth
      `,
    })

    /** What the user may do with the item (from `upFrom`'s rows): null — nothing, not even see it. */
    const roleIn = (user: UserId, up: readonly UpRow[]): Role | null => {
      if (!up.length) return null
      if (up[0]!.owner_id === user) return "owner"
      return up.reduce<Role | null>((best, r) => better(best, r.shared_role), null)
    }

    /** The folders above the item the user can see: all of them in their own library; in someone
     *  else's, those from the highest one shared with them down. */
    const pathIn = (user: UserId, up: readonly UpRow[]): Crumb[] => {
      const above = up.slice(1)
      if (up[0]?.owner_id === user) return above.map((r) => ({ id: r.id, name: r.name })).reverse()
      let top = -1
      above.forEach((r, i) => { if (r.shared_role !== null) top = i })
      return above.slice(0, top + 1).map((r) => ({ id: r.id, name: r.name })).reverse()
    }

    /** The item, if the user may do what `need` takes: its rows up, and the user's role. */
    const access = (user: UserId, id: string, need: Role = "viewer") =>
      upFrom({ user, id }).pipe(
        Effect.orDie,
        Effect.flatMap((up): Effect.Effect<{ up: readonly UpRow[]; role: Role }, NotFound | RoleTooLow> => {
          const role = roleIn(user, up)
          if (role === null) return Effect.fail(new NotFound({ id }))
          if (RANK[role] < RANK[need]) return Effect.fail(new RoleTooLow({ needed: need, role }))
          return Effect.succeed({ up, role })
        }),
      )
    /** Reading needs only to see it. */
    const read = (user: UserId, id: string) => access(user, id).pipe(Effect.catchTag("RoleTooLow", Effect.die))

    /** May the user take the item out of where it is (delete it, move it away)? Its owner may, and
     *  an editor of the folder it is in; one it was shared with on its own, not. */
    const mayTakeOut = (user: UserId, up: readonly UpRow[]) => {
      if (up[0]!.owner_id === user) return true
      const folder = roleIn(user, up.slice(1))
      return folder !== null && RANK[folder] >= RANK.editor
    }

    const cards = (user: UserId, where: ReturnType<typeof whereOf>) => sql`
      SELECT i.id, i.kind, i.name, i.parent_id, i.owner_id, u.name AS owner_name, u.avatar_url AS owner_avatar,
             i.modified, i.saved_at, i.preview,
             (SELECT count(*) FROM items c WHERE c.parent_id = i.id)::int AS count,
             COALESCE((SELECT jsonb_agg(p.preview) FROM (
               SELECT c.preview FROM items c WHERE c.parent_id = i.id AND c.kind = 'note' AND c.preview IS NOT NULL
               ORDER BY c.saved_at DESC LIMIT 4
             ) p), '[]'::jsonb) AS previews,
             (SELECT s.role FROM shares s WHERE s.item_id = i.id AND s.user_id = ${user}) AS shared_role
      FROM items i JOIN users u ON u.id = i.owner_id
      WHERE ${where}
      ORDER BY i.kind = 'folder' DESC, CASE WHEN i.kind = 'folder' THEN lower(i.name) END, i.saved_at DESC, i.id
    `
    const whereOf = (user: UserId, what: { parent: string } | { home: true } | { id: string }) =>
      "parent" in what ? sql`i.parent_id = ${what.parent}`
      : "id" in what ? sql`i.id = ${what.id}`
      : sql`(i.owner_id = ${user} AND i.parent_id IS NULL) OR i.id IN (
          -- shared with the user, and not inside something else shared with them
          SELECT s.item_id FROM shares s WHERE s.user_id = ${user} AND NOT s.hidden AND NOT EXISTS (
            WITH RECURSIVE up(id) AS (
              SELECT parent_id FROM items WHERE id = s.item_id
              UNION ALL
              SELECT i2.parent_id FROM items i2 JOIN up ON i2.id = up.id
            )
            SELECT 1 FROM up JOIN shares s2 ON s2.item_id = up.id AND s2.user_id = ${user}
          )
        )`
    const cardRows = (user: UserId, what: Parameters<typeof whereOf>[1]) =>
      cards(user, whereOf(user, what)).pipe(Effect.flatMap(Schema.decodeUnknown(Schema.Array(CardRow))))

    /** A row as a card; `inherited`: the user's role from the folder it is in (null: at the top). */
    const card = (user: UserId, r: CardRow, inherited: Role | null): ItemCard => ({
      id: r.id, kind: r.kind, name: r.name, parentId: r.parent_id,
      role: r.owner_id === user ? "owner" : better(inherited, r.shared_role) ?? "viewer",
      owner: r.owner_id === user ? null : { name: r.owner_name, avatarUrl: r.owner_avatar },
      modified: r.modified, savedAt: r.saved_at.toISOString(), preview: r.preview, previews: r.previews, count: r.count,
    })

    const cardOf = (user: UserId, id: string, role: Role) =>
      cardRows(user, { id }).pipe(Effect.map(([r]) => ({ ...card(user, r!, null), role })))

    // ------------------------------------------------------------------ reading

    const home = (user: UserId) =>
      cardRows(user, { home: true }).pipe(
        Effect.map((rows) => rows.map((r) => card(user, r, null))),
        Effect.orDie, Effect.withSpan("LibraryRepo.home"),
      )

    const folder = (user: UserId, id: string) =>
      Effect.gen(function* () {
        const { up, role } = yield* read(user, id)
        if (up[0]!.kind !== "folder") return yield* Effect.fail(new NotFound({ id }))
        const self = yield* cardOf(user, id, role).pipe(Effect.orDie)
        const inside = yield* cardRows(user, { parent: id }).pipe(Effect.orDie)
        return { folder: self, path: pathIn(user, up), items: inside.map((r) => card(user, r, role)) } satisfies Folder
      }).pipe(Effect.withSpan("LibraryRepo.folder", { attributes: { id } }))

    /** Every folder the user may put things into: their own, and those under a share that lets them edit. */
    const destinations = (user: UserId) =>
      sql<Destination & { parent_id: string | null }>`
        WITH RECURSIVE down(id) AS (
          SELECT i.id FROM items i WHERE i.kind = 'folder' AND (i.owner_id = ${user} OR i.id IN (
            SELECT item_id FROM shares WHERE user_id = ${user} AND role = 'editor'))
          UNION
          SELECT c.id FROM items c JOIN down ON c.parent_id = down.id WHERE c.kind = 'folder'
        )
        SELECT i.id, i.name, i.parent_id FROM items i JOIN down ON down.id = i.id ORDER BY lower(i.name), i.id
      `.pipe(
        Effect.map((rows) => {
          const ids = new Set(rows.map((r) => r.id))
          // a folder whose parent the user cannot put things into shows at the top
          return rows.map((r): Destination => ({ id: r.id, name: r.name, parentId: r.parent_id && ids.has(r.parent_id) ? r.parent_id : null }))
        }),
        Effect.orDie, Effect.withSpan("LibraryRepo.destinations"),
      )

    const note = (user: UserId, id: string) =>
      Effect.gen(function* () {
        const { up, role } = yield* read(user, id)
        if (up[0]!.kind !== "note") return yield* Effect.fail(new NotFound({ id }))
        const [row] = yield* sql<{ document: unknown; revision: number; saved_at: Date }>`
          SELECT document, revision, saved_at FROM items WHERE id = ${id}`.pipe(Effect.orDie)
        const document = yield* Schema.decodeUnknown(NotebookDocument)(row!.document).pipe(Effect.orDie)
        return { document, revision: row!.revision, savedAt: new Date(row!.saved_at).toISOString(), role, path: pathIn(user, up) } satisfies Note
      }).pipe(Effect.withSpan("LibraryRepo.note", { attributes: { id } }))

    /** Where a new item goes: the folder (the user must edit it; it gives the owner) or the top of the user's own. */
    const into = (user: UserId, parentId: string | null) =>
      Effect.gen(function* () {
        if (parentId === null) return { owner: user, parent: null as string | null }
        const { up } = yield* access(user, parentId, "editor")
        if (up[0]!.kind !== "folder") return yield* Effect.fail(new NotAFolder({ id: parentId }))
        return { owner: up[0]!.owner_id, parent: parentId }
      })

    // ------------------------------------------------------------------ changing

    const createFolder = (user: UserId, name: string, parentId: string | null) =>
      Effect.gen(function* () {
        const { owner, parent } = yield* into(user, parentId)
        const id = newId()
        yield* sql`
          INSERT INTO items (id, owner_id, parent_id, kind, name, revision, saved_at, saved_by)
          VALUES (${id}, ${owner}, ${parent}, 'folder', ${name}, 1, now(), ${user})`.pipe(Effect.orDie)
        return yield* cardOf(user, id, owner === user ? "owner" : "editor").pipe(Effect.orDie)
      }).pipe(Effect.withSpan("LibraryRepo.createFolder"))

    /** Create (baseRevision null; `parentId`: into which folder, else the top) or update a note. */
    const save = (user: UserId, document: NotebookDocument, baseRevision: number | null, parentId?: string | null) =>
      Effect.gen(function* () {
        yield* sql`SELECT pg_advisory_xact_lock(hashtextextended(${document.id}, 0))` // one save of a note at a time
        const [stored] = yield* sql<{ revision: number; kind: string }>`SELECT revision, kind FROM items WHERE id = ${document.id}`
        if (stored) yield* access(user, document.id, "editor") // someone else's, not shared: NotFound
        if (stored ? stored.revision !== baseRevision || stored.kind !== "note" : baseRevision !== null)
          return yield* Effect.fail(new RevisionConflict({ id: document.id, current: stored?.revision ?? 0, base: baseRevision }))
        const revision = (stored?.revision ?? 0) + 1
        const savedAt = DateTime.formatIso(yield* DateTime.now)
        const row = {
          name: document.title, document: yield* Schema.encode(Schema.parseJson(NotebookDocument))(document),
          revision, modified: document.modified, saved_at: savedAt, saved_by: user, cells: document.cells.length,
          schematics: document.cells.filter((c) => c.type === "schematic").length, preview: JSON.stringify(previewOf(document)),
        }
        if (stored) {
          yield* sql`UPDATE items SET ${sql.update(row)} WHERE id = ${document.id}`
        } else {
          const { owner, parent } = yield* into(user, parentId ?? null)
          yield* sql`INSERT INTO items ${sql.insert({ ...row, id: document.id, owner_id: owner, parent_id: parent, kind: "note" })}`
        }
        return { revision, savedAt } satisfies Saved
      }).pipe(
        sql.withTransaction,
        Effect.catchTags({ SqlError: Effect.die, ParseError: Effect.die }),
        Effect.withSpan("LibraryRepo.save", { attributes: { id: document.id, baseRevision } }),
      )

    /** Rename (a note: its title, a new revision) and/or move into another folder of the same owner. */
    const patch = (user: UserId, id: string, change: { name?: string | undefined; parentId?: string | null | undefined }) =>
      Effect.gen(function* () {
        const { up, role } = yield* access(user, id, "editor")
        const it = up[0]!
        if (change.parentId !== undefined && change.parentId !== it.parent_id) {
          if (!mayTakeOut(user, up)) return yield* Effect.fail(new RoleTooLow({ needed: "owner", role }))
          const { owner, parent } = yield* into(user, change.parentId)
          if (owner !== it.owner_id) return yield* Effect.fail(new OtherOwner({ id }))
          if (parent !== null && it.kind === "folder") {
            const above = yield* upFrom({ user, id: parent })
            if (above.some((r) => r.id === id)) return yield* Effect.fail(new MoveIntoItself({ id }))
          }
          yield* sql`UPDATE items SET parent_id = ${parent} WHERE id = ${id}`
        }
        if (change.name !== undefined && change.name !== it.name) {
          yield* it.kind === "folder"
            ? sql`UPDATE items SET name = ${change.name} WHERE id = ${id}`
            : sql`
              UPDATE items SET name = ${change.name}, revision = revision + 1, saved_at = now(), saved_by = ${user},
                     document = jsonb_set(document, '{title}', to_jsonb(${change.name}::text))
              WHERE id = ${id}`
        }
        return yield* cardOf(user, id, role)
      }).pipe(
        sql.withTransaction,
        Effect.catchTags({ SqlError: Effect.die, ParseError: Effect.die }),
        Effect.withSpan("LibraryRepo.patch", { attributes: { id } }),
      )

    /** A folder goes with everything in it. */
    const remove = (user: UserId, id: string) =>
      Effect.gen(function* () {
        const { up, role } = yield* read(user, id)
        if (!mayTakeOut(user, up)) return yield* Effect.fail(new RoleTooLow({ needed: "owner", role }))
        yield* sql`DELETE FROM items WHERE id = ${id}`.pipe(Effect.orDie)
      }).pipe(Effect.withSpan("LibraryRepo.remove", { attributes: { id } }))

    /** A note's address from before folders (its slug in the user's notes then): its id. */
    const legacy = (user: UserId, ref: string) =>
      sql<{ item_id: string }>`SELECT item_id FROM legacy_slugs WHERE owner_id = ${user} AND slug = ${ref}`.pipe(
        Effect.orDie,
        Effect.flatMap(([row]) => row ? Effect.succeed({ id: row.item_id }) : Effect.fail(new NotFound({ id: ref }))),
      )

    return { home, folder, destinations, note, createFolder, save, patch, remove, legacy } as const
  }),
}) {}

