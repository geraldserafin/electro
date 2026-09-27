/** What can go wrong, as the client sees it: each error has its HTTP status and a message. */
import { HttpApiSchema } from "@effect/platform"
import { Schema } from "effect"
import { NoteId } from "./Notebook.js"

export class NoteNotFound extends Schema.TaggedError<NoteNotFound>()(
  "NoteNotFound",
  { id: Schema.String }, // the id or slug asked for
  HttpApiSchema.annotations({ status: 404 }),
) {
  get message() {
    return `Nie ma notatki ${this.id}.`
  }
}

/** The note changed on the server since the client read it (or it exists already). */
export class RevisionConflict extends Schema.TaggedError<RevisionConflict>()(
  "RevisionConflict",
  { id: NoteId, current: Schema.Int, base: Schema.NullOr(Schema.Int) },
  HttpApiSchema.annotations({ status: 409 }),
) {
  get message() {
    return this.base === null
      ? `Notatka ${this.id} już jest na serwerze (wersja ${this.current}).`
      : `Notatka ${this.id} zmieniła się w międzyczasie: na serwerze jest wersja ${this.current}, a zapis był od ${this.base}.`
  }
}

/** The address and the document name different notes. */
export class NoteIdMismatch extends Schema.TaggedError<NoteIdMismatch>()(
  "NoteIdMismatch",
  { path: NoteId, document: NoteId },
  HttpApiSchema.annotations({ status: 400 }),
) {
  get message() {
    return `Adres wskazuje notatkę ${this.path}, a dokument to ${this.document}.`
  }
}
