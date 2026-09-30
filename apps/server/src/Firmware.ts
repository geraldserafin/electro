/** Firmware files (@electro/notes-api: Firmware.ts) in the database, and their endpoints: an upload kept
 *  once by its SHA-256, a file fetched by it — its bytes, which never change (cached for good). */

import { createHash } from "node:crypto";
import { HttpApiBuilder, HttpServerResponse } from "@effect/platform";
import { SqlClient } from "@effect/sql";
import {
  CurrentUser,
  FIRMWARE_MAX,
  FIRMWARE_QUOTA,
  FirmwareNotFound,
  FirmwareQuota,
  FirmwareSize,
  NotesApi,
} from "@electro/notes-api";
import { Effect } from "effect";

export const FirmwareLive = HttpApiBuilder.group(NotesApi, "firmware", (handlers) =>
  Effect.gen(function* () {
    const sql = yield* SqlClient.SqlClient;
    return handlers.handle("upload", ({ payload }) =>
      Effect.gen(function* () {
        const user = yield* CurrentUser;
        const size = payload.length;
        if (size === 0 || size > FIRMWARE_MAX) return yield* Effect.fail(new FirmwareSize({ size, max: FIRMWARE_MAX }));
        const id = createHash("sha256").update(payload).digest("hex");
        const [kept] = yield* sql<{ id: string }>`SELECT id FROM firmware WHERE id = ${id}`.pipe(Effect.orDie);
        if (kept) return { id, size }; // (someone uploaded it before: nothing new to keep)
        const [{ used }] = yield* sql<{ used: string }>`
          SELECT coalesce(sum(size), 0) AS used FROM firmware WHERE uploaded_by = ${user.id}`.pipe(Effect.orDie);
        if (Number(used) + size > FIRMWARE_QUOTA)
          return yield* Effect.fail(new FirmwareQuota({ used: Number(used), quota: FIRMWARE_QUOTA }));
        yield* sql`
          INSERT INTO firmware (id, bytes, size, uploaded_by) VALUES (${id}, ${Buffer.from(payload)}, ${size}, ${user.id})
          ON CONFLICT (id) DO NOTHING`.pipe(Effect.orDie);
        return { id, size };
      }).pipe(Effect.withSpan("Firmware.upload")),
    );
  }),
);

export const FirmwareFilesLive = HttpApiBuilder.group(NotesApi, "firmwareFiles", (handlers) =>
  Effect.gen(function* () {
    const sql = yield* SqlClient.SqlClient;
    return handlers.handle("get", ({ path }) =>
      Effect.gen(function* () {
        const [row] = /^[0-9a-f]{64}$/.test(path.id)
          ? yield* sql<{ bytes: Uint8Array }>`SELECT bytes FROM firmware WHERE id = ${path.id}`.pipe(Effect.orDie)
          : [];
        if (!row) return yield* Effect.fail(new FirmwareNotFound({ id: path.id }));
        return HttpServerResponse.uint8Array(new Uint8Array(row.bytes), {
          contentType: "application/octet-stream",
          headers: { "cache-control": "public, max-age=31536000, immutable" },
        });
      }).pipe(Effect.withSpan("Firmware.get")),
    );
  }),
);
