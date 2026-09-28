import { SqlClient } from "@effect/sql"
import { Effect } from "effect"

/**
 * Notes, each user's their own: ids and addresses (slugs) are unique per owner. The document is
 * stored whole; title, counts and the first page's preview are copied out so a list needs no
 * parsing. The slugs a note had before stay in note_slugs, so old links keep finding it.
 */
export default Effect.gen(function* () {
  const sql = yield* SqlClient.SqlClient
  yield* sql`
    CREATE TABLE notes (
      owner_id    uuid NOT NULL REFERENCES users ON DELETE CASCADE,
      id          text NOT NULL,
      slug        text NOT NULL,
      title       text NOT NULL,
      document    jsonb NOT NULL,
      revision    integer NOT NULL,
      modified    text NOT NULL,  -- the document's own stamp, as the client wrote it
      saved_at    timestamptz NOT NULL,
      cells       integer NOT NULL,
      schematics  integer NOT NULL,
      preview     jsonb NOT NULL,
      PRIMARY KEY (owner_id, id),
      UNIQUE (owner_id, slug)
    )
  `
  yield* sql`CREATE INDEX notes_by_saved_at ON notes (owner_id, saved_at DESC)`
  yield* sql`
    CREATE TABLE note_slugs (
      owner_id  uuid NOT NULL,
      slug      text NOT NULL,
      note_id   text NOT NULL,
      PRIMARY KEY (owner_id, slug),
      FOREIGN KEY (owner_id, note_id) REFERENCES notes (owner_id, id) ON DELETE CASCADE
    )
  `
})
