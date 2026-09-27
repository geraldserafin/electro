/** The HTTP side: the contract's endpoints, implemented with NotesRepo. */
import { HttpApiBuilder } from "@effect/platform"
import { NoteIdMismatch, NotesApi } from "@electro/notes-api"
import { Effect, Layer } from "effect"
import { NotesRepo } from "./NotesRepo.js"

export const NotesLive = HttpApiBuilder.group(NotesApi, "notes", (handlers) =>
  Effect.gen(function* () {
    const repo = yield* NotesRepo
    return handlers
      .handle("list", () => repo.list)
      .handle("get", ({ path }) => repo.get(path.ref))
      .handle("save", ({ path, payload }) =>
        payload.document.id !== path.id
          ? Effect.fail(new NoteIdMismatch({ path: path.id, document: payload.document.id }))
          : repo.save(payload.document, payload.baseRevision))
      .handle("remove", ({ path }) => repo.remove(path.id))
  }))

export const SystemLive = HttpApiBuilder.group(NotesApi, "system", (handlers) =>
  handlers.handle("health", () => Effect.succeed({ ok: true as const })))

/** The whole API; needs a NotesRepo (and so a database). */
export const ApiLive = HttpApiBuilder.api(NotesApi).pipe(
  Layer.provide([NotesLive, SystemLive]),
  Layer.provide(NotesRepo.Default),
)
