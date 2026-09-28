import { SqlClient } from "@effect/sql"
import { Effect } from "effect"
import { randomUUID } from "node:crypto"

/**
 * Folders: each user's notes in folders, folders in folders; and shares — a note or a folder
 * (with everything in it) for someone else to read or edit. Ids are global now (an address is an
 * id: /n/<id>), so the notes move from `notes` (ids unique per owner) into `items` at the top of
 * their owner's library, keeping ids (a clash between two owners: the later note gets a new one),
 * revisions and when they were saved. Their old addresses (/notes/<slug>, older slugs too) stay
 * in `legacy_slugs`, for the redirect; `notes` and `note_slugs` go.
 *
 * `share_links` is for sharing by link (a later step): here already, so the tables stay put.
 */
export default Effect.gen(function* () {
  const sql = yield* SqlClient.SqlClient
  yield* sql`
    CREATE TABLE items (
      id          text PRIMARY KEY,
      owner_id    uuid NOT NULL REFERENCES users ON DELETE CASCADE,
      parent_id   text REFERENCES items ON DELETE CASCADE,  -- a folder; null: the top of the owner's library
      kind        text NOT NULL CHECK (kind IN ('folder', 'note')),
      name        text NOT NULL,  -- a note's: its document's title
      document    jsonb,  -- a note's; null for a folder
      revision    integer NOT NULL,
      modified    text,  -- the document's own stamp, as the client wrote it
      saved_at    timestamptz NOT NULL,
      saved_by    uuid REFERENCES users ON DELETE SET NULL,
      cells       integer NOT NULL DEFAULT 0,
      schematics  integer NOT NULL DEFAULT 0,
      preview     jsonb,
      CHECK ((kind = 'note') = (document IS NOT NULL))
    )
  `
  yield* sql`CREATE INDEX items_by_parent ON items (parent_id)`
  yield* sql`CREATE INDEX items_at_top ON items (owner_id) WHERE parent_id IS NULL`
  yield* sql`
    CREATE TABLE shares (
      item_id   text NOT NULL REFERENCES items ON DELETE CASCADE,
      user_id   uuid NOT NULL REFERENCES users ON DELETE CASCADE,
      role      text NOT NULL CHECK (role IN ('editor', 'viewer')),
      added_by  uuid REFERENCES users ON DELETE SET NULL,
      added_at  timestamptz NOT NULL DEFAULT now(),
      hidden    boolean NOT NULL DEFAULT false,  -- taken off the user's home screen (still theirs to open)
      PRIMARY KEY (item_id, user_id)
    )
  `
  yield* sql`CREATE INDEX shares_by_user ON shares (user_id)`
  yield* sql`
    CREATE TABLE share_links (
      token_hash  text PRIMARY KEY,  -- sha256 of the token in the link
      item_id     text NOT NULL REFERENCES items ON DELETE CASCADE,
      role        text NOT NULL CHECK (role IN ('editor', 'viewer')),
      created_by  uuid REFERENCES users ON DELETE SET NULL,
      expires_at  timestamptz NOT NULL
    )
  `
  yield* sql`
    CREATE TABLE legacy_slugs (
      owner_id  uuid NOT NULL REFERENCES users ON DELETE CASCADE,
      slug      text NOT NULL,
      item_id   text NOT NULL REFERENCES items ON DELETE CASCADE,
      PRIMARY KEY (owner_id, slug)
    )
  `

  const notes = yield* sql<{ owner_id: string; id: string }>`SELECT owner_id, id FROM notes ORDER BY saved_at, owner_id`
  for (const { owner_id, id } of notes) {
    const [clash] = yield* sql<{ id: string }>`SELECT id FROM items WHERE id = ${id}`
    const newId = clash ? randomUUID().replaceAll("-", "") : id
    yield* sql`
      INSERT INTO items (id, owner_id, parent_id, kind, name, document, revision, modified, saved_at, saved_by,
                         cells, schematics, preview)
      SELECT ${newId}, owner_id, NULL, 'note', title, jsonb_set(document, '{id}', to_jsonb(${newId}::text)),
             revision, modified, saved_at, owner_id, cells, schematics, preview
      FROM notes WHERE owner_id = ${owner_id} AND id = ${id}
    `
    yield* sql`
      INSERT INTO legacy_slugs (owner_id, slug, item_id)
      SELECT owner_id, slug, ${newId} FROM notes WHERE owner_id = ${owner_id} AND id = ${id}
      UNION
      SELECT owner_id, slug, ${newId} FROM note_slugs WHERE owner_id = ${owner_id} AND note_id = ${id}
    `
  }
  yield* sql`DROP TABLE note_slugs`
  yield* sql`DROP TABLE notes`
})
