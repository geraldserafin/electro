/**
 * Who has an item, in the database: shares with people (`shares`) and the item's link
 * (`share_links`). Only the owner sees or changes them (LibraryRepo's `access`, as "owner");
 * whoever opens a link gets a share with its role — a better one they had stays.
 */

import { randomBytes } from "node:crypto";
import { SqlClient } from "@effect/sql";
import { type Joined, NoSuchPerson, NotFound, type ShareRole, type Sharing, type UserId } from "@electro/notes-api";
import { Effect } from "effect";
import { LibraryRepo } from "./LibraryRepo.js";

const newToken = () => randomBytes(18).toString("base64url");

export class SharingRepo extends Effect.Service<SharingRepo>()("SharingRepo", {
  effect: Effect.gen(function* () {
    const sql = yield* SqlClient.SqlClient;
    const library = yield* LibraryRepo;

    /** Who has the item (the user must own it). */
    const sharing = (id: string) =>
      Effect.gen(function* () {
        const [owner] = yield* sql<{ name: string; avatar_url: string | null }>`
          SELECT u.name, u.avatar_url FROM items i JOIN users u ON u.id = i.owner_id WHERE i.id = ${id}`;
        const people = yield* sql<{
          id: UserId;
          name: string;
          email: string | null;
          avatar_url: string | null;
          role: ShareRole;
        }>`
          SELECT u.id, u.name, u.email, u.avatar_url, s.role FROM shares s JOIN users u ON u.id = s.user_id
          WHERE s.item_id = ${id} ORDER BY s.added_at, lower(u.name)`;
        const [link] = yield* sql<{
          token: string;
          role: ShareRole;
        }>`SELECT token, role FROM share_links WHERE item_id = ${id}`;
        return {
          owner: { name: owner!.name, avatarUrl: owner!.avatar_url },
          people: people.map((p) => ({
            id: p.id,
            name: p.name,
            email: p.email,
            avatarUrl: p.avatar_url,
            role: p.role,
          })),
          link: link ? { token: link.token, role: link.role } : null,
        } satisfies Sharing;
      }).pipe(Effect.orDie);

    /** Does `change` to the item the user owns, then says who has it. */
    const owned = <E = never>(
      user: UserId,
      id: string,
      change: Effect.Effect<unknown, E> = Effect.void,
      span = "get",
    ) =>
      library
        .access(user, id, "owner")
        .pipe(
          Effect.zipRight(change),
          Effect.zipRight(sharing(id)),
          Effect.withSpan(`SharingRepo.${span}`, { attributes: { id } }),
        );

    const get = (user: UserId, id: string) => owned(user, id);

    const add = (user: UserId, id: string, email: string, role: ShareRole) =>
      owned(
        user,
        id,
        Effect.gen(function* () {
          const [person] = yield* sql<{ id: string }>`SELECT id FROM users WHERE lower(email) = lower(${email})`.pipe(
            Effect.orDie,
          );
          if (!person) return yield* Effect.fail(new NoSuchPerson({ email }));
          if (person.id === user) return; // the owner has it already
          yield* sql`
          INSERT INTO shares (item_id, user_id, role, added_by) VALUES (${id}, ${person.id}, ${role}, ${user})
          ON CONFLICT (item_id, user_id) DO UPDATE SET role = excluded.role`.pipe(Effect.orDie);
        }),
        "add",
      );

    const setRole = (user: UserId, id: string, who: UserId, role: ShareRole) =>
      owned(
        user,
        id,
        sql`UPDATE shares SET role = ${role} WHERE item_id = ${id} AND user_id = ${who}`.pipe(Effect.orDie),
        "setRole",
      );

    const unshare = (user: UserId, id: string, who: UserId) =>
      owned(user, id, sql`DELETE FROM shares WHERE item_id = ${id} AND user_id = ${who}`.pipe(Effect.orDie), "unshare");

    const leave = (user: UserId, id: string) =>
      sql<{ item_id: string }>`DELETE FROM shares WHERE item_id = ${id} AND user_id = ${user} RETURNING item_id`.pipe(
        Effect.orDie,
        Effect.flatMap((rows) => (rows.length ? Effect.void : Effect.fail(new NotFound({ id })))),
        Effect.withSpan("SharingRepo.leave", { attributes: { id } }),
      );

    const link = (user: UserId, id: string, role: ShareRole) =>
      owned(
        user,
        id,
        sql`
        INSERT INTO share_links (item_id, token, role, created_by) VALUES (${id}, ${newToken()}, ${role}, ${user})
        ON CONFLICT (item_id) DO UPDATE SET role = excluded.role`.pipe(Effect.orDie),
        "link",
      );

    const newLink = (user: UserId, id: string) =>
      owned(
        user,
        id,
        sql`
        INSERT INTO share_links (item_id, token, role, created_by) VALUES (${id}, ${newToken()}, 'viewer', ${user})
        ON CONFLICT (item_id) DO UPDATE SET token = excluded.token, created_by = excluded.created_by, created_at = now()`.pipe(
          Effect.orDie,
        ),
        "newLink",
      );

    const unlink = (user: UserId, id: string) =>
      owned(user, id, sql`DELETE FROM share_links WHERE item_id = ${id}`.pipe(Effect.orDie), "unlink");

    /** Opening a link: the item shared with the user (with the link's role, or the better one they
     *  had), back on their home screen. */
    const join = (user: UserId, token: string) =>
      Effect.gen(function* () {
        const [found] = yield* sql<{
          id: string;
          kind: "folder" | "note";
          name: string;
          owner_id: string;
          role: ShareRole;
        }>`
          SELECT i.id, i.kind, i.name, i.owner_id, l.role FROM share_links l JOIN items i ON i.id = l.item_id
          WHERE l.token = ${token}`.pipe(Effect.orDie);
        if (!found) return yield* Effect.fail(new NotFound({ id: "link" }));
        if (found.owner_id !== user) {
          yield* sql`
            INSERT INTO shares (item_id, user_id, role, added_by) VALUES (${found.id}, ${user}, ${found.role}, NULL)
            ON CONFLICT (item_id, user_id) DO UPDATE
              SET role = CASE WHEN shares.role = 'editor' THEN 'editor' ELSE excluded.role END, hidden = false`.pipe(
            Effect.orDie,
          );
        }
        return { id: found.id, kind: found.kind, name: found.name } satisfies Joined;
      }).pipe(Effect.withSpan("SharingRepo.join"));

    return { get, add, setRole, unshare, leave, link, newLink, unlink, join } as const;
  }),
  dependencies: [LibraryRepo.Default],
}) {}
