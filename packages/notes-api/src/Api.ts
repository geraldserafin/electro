/**
 * The notes API: the one description of the endpoints, used by the server (to implement them)
 * and by the notebook (to call them, with typed results and errors). Notes are
 * private: each user sees only their own, and without a session the notes endpoints answer 401.
 */
import { HttpApi, HttpApiEndpoint, HttpApiGroup } from "@effect/platform"
import { Schema } from "effect"
import { AuthGroup, Authentication } from "./Auth.js"
import { NoteIdMismatch, NoteNotFound, RevisionConflict } from "./Errors.js"
import { Note, NoteId, NoteRef, NoteSummary, Saved, SaveNote } from "./Notebook.js"

const ById = Schema.Struct({ id: NoteId })

export class NotesGroup extends HttpApiGroup.make("notes")
  .add(
    HttpApiEndpoint.get("list", "/notes")
      .addSuccess(Schema.Array(NoteSummary)),
  )
  .add(
    // by address: the slug (a current or an older one) or the id
    HttpApiEndpoint.get("get", "/notes/:ref")
      .setPath(Schema.Struct({ ref: NoteRef }))
      .addSuccess(Note)
      .addError(NoteNotFound),
  )
  .add(
    // create (baseRevision: null) or update (baseRevision: the revision it was read at)
    HttpApiEndpoint.put("save", "/notes/:id")
      .setPath(ById)
      .setPayload(SaveNote)
      .addSuccess(Saved)
      .addError(RevisionConflict)
      .addError(NoteIdMismatch),
  )
  .add(
    HttpApiEndpoint.del("remove", "/notes/:id")
      .setPath(ById)
      .addSuccess(Schema.Void)
      .addError(NoteNotFound),
  )
  .middleware(Authentication)
{}

export class SystemGroup extends HttpApiGroup.make("system")
  .add(HttpApiEndpoint.get("health", "/health").addSuccess(Schema.Struct({ ok: Schema.Literal(true) })))
{}

export class NotesApi extends HttpApi.make("notes")
  .add(NotesGroup)
  .add(AuthGroup)
  .add(SystemGroup)
  .prefix("/api")
{}
