/**
 * Users and their sessions. Signing in with a provider finds the user by that provider's account,
 * else by the verified email (a second provider, the same person), else makes a new one. A
 * session is a random token: the cookie has it, the database only its hash.
 */

import { createHash, randomBytes } from "node:crypto";
import { SqlClient, SqlSchema } from "@effect/sql";
import { type Provider, User, UserId } from "@electro/notes-api";
import { Effect, Option, Schema } from "effect";

/** What a provider says about who signed in. */
export interface Profile {
  readonly provider: Provider;
  readonly id: string; // the provider's own id for them
  readonly name: string;
  readonly email: string | null; // only one the provider verified
  readonly avatarUrl: string | null;
}

/** How long a session lasts (the cookie as long). */
export const SESSION_DAYS = 30;

const hash = (token: string) => createHash("sha256").update(token).digest("hex");

const UserRow = Schema.Struct({
  id: UserId,
  name: Schema.String,
  email: Schema.NullOr(Schema.String),
  avatar_url: Schema.NullOr(Schema.String),
});
const toUser = (r: typeof UserRow.Type) =>
  new User({ id: r.id, name: r.name, email: r.email, avatarUrl: r.avatar_url });

export class Accounts extends Effect.Service<Accounts>()("Accounts", {
  effect: Effect.gen(function* () {
    const sql = yield* SqlClient.SqlClient;

    const IdRow = Schema.Struct({ id: UserId });
    const byAccount = SqlSchema.findOne({
      Request: Schema.Struct({ provider: Schema.String, id: Schema.String }),
      Result: IdRow,
      execute: ({ provider, id }) =>
        sql`SELECT user_id AS id FROM accounts WHERE provider = ${provider} AND provider_user_id = ${id}`,
    });
    const byEmail = SqlSchema.findOne({
      Request: Schema.String,
      Result: IdRow,
      execute: (email) => sql`SELECT id FROM users WHERE email = ${email}`,
    });
    const insertUser = SqlSchema.single({
      Request: Schema.Struct({
        name: Schema.String,
        email: Schema.NullOr(Schema.String),
        avatar_url: Schema.NullOr(Schema.String),
      }),
      Result: IdRow,
      execute: (row) => sql`INSERT INTO users ${sql.insert(row)} RETURNING id`,
    });
    const bySession = SqlSchema.findOne({
      Request: Schema.String,
      Result: UserRow,
      execute: (id) => sql`
        SELECT users.id, users.name, users.email, users.avatar_url
        FROM sessions JOIN users ON users.id = sessions.user_id
        WHERE sessions.id = ${id} AND sessions.expires_at > now()
      `,
    });

    /** The user `profile` is (made on the first sign-in); name and picture as the provider has them now. */
    const signIn = (profile: Profile) =>
      Effect.gen(function* () {
        const known = yield* byAccount({ provider: profile.provider, id: profile.id });
        if (Option.isSome(known)) {
          yield* sql`UPDATE users SET name = ${profile.name}, avatar_url = coalesce(${profile.avatarUrl}, avatar_url)
                     WHERE id = ${known.value.id}`;
          return known.value.id;
        }
        const sameEmail = profile.email === null ? Option.none() : yield* byEmail(profile.email);
        const id = Option.isSome(sameEmail)
          ? sameEmail.value.id
          : (yield* insertUser({ name: profile.name, email: profile.email, avatar_url: profile.avatarUrl })).id;
        yield* sql`INSERT INTO accounts ${sql.insert({ provider: profile.provider, provider_user_id: profile.id, user_id: id })}`;
        return id;
      }).pipe(
        sql.withTransaction,
        Effect.orDie,
        Effect.withSpan("Accounts.signIn", { attributes: { provider: profile.provider } }),
      );

    /** A new session for `user`: the token for the cookie. */
    const startSession = (user: UserId) =>
      Effect.gen(function* () {
        const token = randomBytes(32).toString("base64url");
        yield* sql`DELETE FROM sessions WHERE expires_at <= now()`; // the expired ones, while here
        yield* sql`INSERT INTO sessions (id, user_id, expires_at)
                   VALUES (${hash(token)}, ${user}, now() + make_interval(days => ${SESSION_DAYS}))`;
        return token;
      }).pipe(Effect.orDie, Effect.withSpan("Accounts.startSession"));

    /** Who the token signs in, if it is a live session. */
    const userOf = (token: string) =>
      bySession(hash(token)).pipe(Effect.map(Option.map(toUser)), Effect.orDie, Effect.withSpan("Accounts.userOf"));

    const endSession = (token: string) =>
      sql`DELETE FROM sessions WHERE id = ${hash(token)}`.pipe(Effect.asVoid, Effect.orDie);

    return { signIn, startSession, userOf, endSession } as const;
  }),
}) {}
