/**
 * The notes API: the one description of the endpoints, used by the server (to implement them)
 * and by the notebook (to call them, with typed results and errors). For now there is a single,
 * implicit user; per-user notes will add authentication middleware to the group, not new paths.
 */
import { HttpApi, HttpApiEndpoint, HttpApiGroup } from "@effect/platform"
import { Schema } from "effect"
import { NoteIdMismatch, NoteNotFound, RevisionConflict } from "./Errors.js"
import { Note, NoteId, NoteSummary, Saved, SaveNote } from "./Notebook.js"

const ById = Schema.Struct({ id: NoteId })

export class NotesGroup extends HttpApiGroup.make("notes")
  .add(
    HttpApiEndpoint.get("list", "/notes")
      .addSuccess(Schema.Array(NoteSummary)),
  )
  .add(
    HttpApiEndpoint.get("get", "/notes/:id")
      .setPath(ById)
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
{}

export class SystemGroup extends HttpApiGroup.make("system")
  .add(HttpApiEndpoint.get("health", "/health").addSuccess(Schema.Struct({ ok: Schema.Literal(true) })))
{}

export class NotesApi extends HttpApi.make("notes")
  .add(NotesGroup)
  .add(SystemGroup)
  .prefix("/api")
{}
