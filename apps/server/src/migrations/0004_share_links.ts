import { SqlClient } from "@effect/sql";
import { Effect } from "effect";

/**
 * Links, as sharing needs them: one per item, and its owner can copy it again whenever they like
 * (as in Google Docs) — so the token itself is kept, not a hash of it; it stops working when a new
 * one is made or the link is taken away, not by a date. The table was empty (no endpoints made
 * any), so it is made anew.
 */
export default Effect.gen(function* () {
  const sql = yield* SqlClient.SqlClient;
  yield* sql`DROP TABLE share_links`;
  yield* sql`
    CREATE TABLE share_links (
      item_id     text PRIMARY KEY REFERENCES items ON DELETE CASCADE,
      token       text NOT NULL UNIQUE,
      role        text NOT NULL CHECK (role IN ('editor', 'viewer')),
      created_by  uuid REFERENCES users ON DELETE SET NULL,
      created_at  timestamptz NOT NULL DEFAULT now()
    )
  `;
});
