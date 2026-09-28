import { SqlClient } from "@effect/sql"
import { Effect } from "effect"

/**
 * Who signs in. A user has one account per provider they signed in with (Google, GitHub,
 * Microsoft); two providers vouching for the same email are the same user. A session is the
 * cookie's token, stored hashed: a leaked table does not sign anyone in.
 */
export default Effect.gen(function* () {
  const sql = yield* SqlClient.SqlClient
  yield* sql`
    CREATE TABLE users (
      id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      name        text NOT NULL,
      email       text UNIQUE,  -- verified by the provider, or null
      avatar_url  text,
      created_at  timestamptz NOT NULL DEFAULT now()
    )
  `
  yield* sql`
    CREATE TABLE accounts (
      provider          text NOT NULL,
      provider_user_id  text NOT NULL,
      user_id           uuid NOT NULL REFERENCES users ON DELETE CASCADE,
      PRIMARY KEY (provider, provider_user_id)
    )
  `
  yield* sql`
    CREATE TABLE sessions (
      id          text PRIMARY KEY,  -- sha256 of the token in the cookie
      user_id     uuid NOT NULL REFERENCES users ON DELETE CASCADE,
      expires_at  timestamptz NOT NULL
    )
  `
  yield* sql`CREATE INDEX sessions_by_user ON sessions (user_id)`
})
