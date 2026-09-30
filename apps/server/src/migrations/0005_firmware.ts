import { SqlClient } from "@effect/sql"
import { Effect } from "effect"

/**
 * Firmware files (@electro/notes-api: Firmware.ts): kept by the SHA-256 of their bytes — the same file
 * uploaded twice, by anyone, is one row (its first uploader's: what counts against their quota).
 */
export default Effect.gen(function* () {
  const sql = yield* SqlClient.SqlClient
  yield* sql`
    CREATE TABLE firmware (
      id           text PRIMARY KEY,  -- sha256 of bytes, hex
      bytes        bytea NOT NULL,
      size         integer NOT NULL,
      uploaded_by  uuid REFERENCES users ON DELETE SET NULL,
      created_at   timestamptz NOT NULL DEFAULT now()
    )
  `
  yield* sql`CREATE INDEX firmware_uploaded_by ON firmware (uploaded_by)`
})
