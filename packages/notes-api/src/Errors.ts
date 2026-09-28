/** What can go wrong, as the client sees it: each error has its HTTP status; the client says it
 *  by its _tag (in the reader's language). ``message``: for logs, in English. */
import { HttpApiSchema } from "@effect/platform"
import { Schema } from "effect"
import { NoteId } from "./Notebook.js"

/** The note changed on the server since the client read it (or it exists already). */
export class RevisionConflict extends Schema.TaggedError<RevisionConflict>()(
  "RevisionConflict",
  { id: NoteId, current: Schema.Int, base: Schema.NullOr(Schema.Int) },
  HttpApiSchema.annotations({ status: 409 }),
) {
  get message() {
    return this.base === null
      ? `Note ${this.id} is already on the server (revision ${this.current}).`
      : `Note ${this.id} changed meanwhile: the server has revision ${this.current}, the save was based on ${this.base}.`
  }
}

/** The address and the document name different notes. */
export class NoteIdMismatch extends Schema.TaggedError<NoteIdMismatch>()(
  "NoteIdMismatch",
  { path: NoteId, document: NoteId },
  HttpApiSchema.annotations({ status: 400 }),
) {
  get message() {
    return `The address names note ${this.path}, the document is ${this.document}.`
  }
}
