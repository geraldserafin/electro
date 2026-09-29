/**
 * The library: each user's folders and notes, folders in folders as deep as they like. Anything
 * may be shared — a note, or a folder with everything in it. What a user may do with an item is
 * the best of: owning it (owner), a share of it or of a folder above it (editor / viewer). To
 * anyone else it is simply not there (NotFound, never "forbidden").
 *
 * Addresses are ids (``/n/<id>/<name>``, ``/f/<id>/<name>``: the name only for reading), so a
 * link never breaks, whatever is renamed or moved. A folder's contents come folders first (by
 * name), then notes (the newest first).
 */
import { HttpApiEndpoint, HttpApiGroup, HttpApiSchema } from "@effect/platform"
import { Schema } from "effect"
import { Authentication } from "./Auth.js"
import { NoteIdMismatch, RevisionConflict } from "./Errors.js"
import { NotebookDocument, NoteId, NotePreview } from "./Notebook.js"

export const Role = Schema.Literal("owner", "editor", "viewer")
export type Role = typeof Role.Type

/** What a role may do, from the least: viewer reads, editor also writes, owner also shares and deletes. */
export const RANK: Record<Role, number> = { viewer: 0, editor: 1, owner: 2 }

export const ItemKind = Schema.Literal("folder", "note")
export type ItemKind = typeof ItemKind.Type

/** Someone, as others see them. */
export const Person = Schema.Struct({ name: Schema.String, avatarUrl: Schema.NullOr(Schema.String) })

/** A card in a grid: a folder (a few of its notes' first pages, for its picture) or a note. */
export const ItemCard = Schema.Struct({
  id: NoteId,
  kind: ItemKind,
  name: Schema.String,
  parentId: Schema.NullOr(NoteId),
  role: Role, // what the user may do with it
  owner: Schema.NullOr(Person), // someone else's (shared with the user): whose; the user's own: null
  modified: Schema.NullOr(Schema.String), // a note's own stamp; a folder's newest note's
  savedAt: Schema.String,
  preview: Schema.NullOr(NotePreview), // a note's first page
  previews: Schema.Array(NotePreview), // a folder's: up to four of its notes, the newest first
  count: Schema.Int, // a folder's: what is in it
  shared: Schema.Boolean, // the user's own, shared with someone (or by a link)
}).annotations({ identifier: "ItemCard" })
export type ItemCard = typeof ItemCard.Type

/** A folder above an item, as far up as the user can see (a link in the breadcrumbs). */
export const Crumb = Schema.Struct({ id: NoteId, name: Schema.String })
export type Crumb = typeof Crumb.Type

export const Folder = Schema.Struct({
  folder: ItemCard,
  path: Schema.Array(Crumb), // from the top down, without the folder itself
  items: Schema.Array(ItemCard),
}).annotations({ identifier: "Folder" })
export type Folder = typeof Folder.Type

/** A folder the user may put things into: for "Move to…". */
export const Destination = Schema.Struct({ id: NoteId, name: Schema.String, parentId: Schema.NullOr(NoteId) })
export type Destination = typeof Destination.Type

/** A stored note: the document, its revision (for saving without overwriting newer work), where it is. */
export const Note = Schema.Struct({
  document: NotebookDocument,
  revision: Schema.Int,
  savedAt: Schema.String,
  role: Role,
  path: Schema.Array(Crumb),
}).annotations({ identifier: "Note" })
export type Note = typeof Note.Type

/** Saving a note: the revision the client started from (null for a new note; anything else than
 *  the stored one is a conflict); a new note also says which folder it goes into (null: the top). */
export const SaveNote = Schema.Struct({
  document: NotebookDocument,
  baseRevision: Schema.NullOr(Schema.Int),
  parentId: Schema.optional(Schema.NullOr(NoteId)),
}).annotations({ identifier: "SaveNote" })
export type SaveNote = typeof SaveNote.Type

export const Saved = Schema.Struct({ revision: Schema.Int, savedAt: Schema.String })
export type Saved = typeof Saved.Type

const Name = Schema.NonEmptyTrimmedString.pipe(Schema.maxLength(200))

export const NewFolder = Schema.Struct({ name: Name, parentId: Schema.NullOr(NoteId) })

/** Renaming and moving: what is given changes. A note's name is its document's title (renamed: a
 *  new revision). */
export const ItemPatch = Schema.Struct({
  name: Schema.optional(Name),
  parentId: Schema.optional(Schema.NullOr(NoteId)),
})

// ------------------------------------------------------------------ errors

/** Not there, or not the user's to see. */
export class NotFound extends Schema.TaggedError<NotFound>()(
  "NotFound",
  { id: Schema.String },
  HttpApiSchema.annotations({ status: 404 }),
) {
  get message() {
    return `No ${this.id} (or not yours to see).`
  }
}

/** A role that does not allow it (a viewer saving; an editor deleting what was shared with them). */
export class RoleTooLow extends Schema.TaggedError<RoleTooLow>()(
  "RoleTooLow",
  { needed: Role, role: Role },
  HttpApiSchema.annotations({ status: 403 }),
) {
  get message() {
    return `This needs the role ${this.needed}; you are ${this.role}.`
  }
}

/** A folder moved into itself or into a folder inside it. */
export class MoveIntoItself extends Schema.TaggedError<MoveIntoItself>()(
  "MoveIntoItself",
  { id: NoteId },
  HttpApiSchema.annotations({ status: 400 }),
) {
  get message() {
    return `Folder ${this.id} cannot go into itself.`
  }
}

/** Something put into what is not a folder (a note). */
export class NotAFolder extends Schema.TaggedError<NotAFolder>()(
  "NotAFolder",
  { id: NoteId },
  HttpApiSchema.annotations({ status: 400 }),
) {
  get message() {
    return `${this.id} is not a folder.`
  }
}

/** Moved between two people's things (out of a folder shared with the user into their own, say). */
export class OtherOwner extends Schema.TaggedError<OtherOwner>()(
  "OtherOwner",
  { id: NoteId },
  HttpApiSchema.annotations({ status: 400 }),
) {
  get message() {
    return `${this.id} cannot move into someone else's folder.`
  }
}

// ------------------------------------------------------------------ endpoints

const ById = Schema.Struct({ id: NoteId })

export class LibraryGroup extends HttpApiGroup.make("library")
  // the top: the user's own folders and notes, and what others shared with them
  .add(HttpApiEndpoint.get("home", "/home").addSuccess(Schema.Array(ItemCard)))
  .add(HttpApiEndpoint.get("folder", "/folders/:id").setPath(ById).addSuccess(Folder).addError(NotFound))
  // every folder the user may put things into
  .add(HttpApiEndpoint.get("destinations", "/destinations").addSuccess(Schema.Array(Destination)))
  .add(
    HttpApiEndpoint.post("createFolder", "/folders")
      .setPayload(NewFolder)
      .addSuccess(ItemCard).addError(NotFound).addError(RoleTooLow).addError(NotAFolder),
  )
  .add(HttpApiEndpoint.get("note", "/notes/:id").setPath(ById).addSuccess(Note).addError(NotFound))
  .add(
    // create (baseRevision: null) or update (baseRevision: the revision it was read at)
    HttpApiEndpoint.put("save", "/notes/:id")
      .setPath(ById).setPayload(SaveNote)
      .addSuccess(Saved)
      .addError(NotFound).addError(RoleTooLow).addError(RevisionConflict).addError(NoteIdMismatch).addError(NotAFolder),
  )
  .add(
    HttpApiEndpoint.patch("patch", "/items/:id")
      .setPath(ById).setPayload(ItemPatch)
      .addSuccess(ItemCard)
      .addError(NotFound).addError(RoleTooLow).addError(MoveIntoItself).addError(NotAFolder).addError(OtherOwner),
  )
  .add(
    // a folder goes with everything in it
    HttpApiEndpoint.del("remove", "/items/:id")
      .setPath(ById).addSuccess(Schema.Void).addError(NotFound).addError(RoleTooLow),
  )
  // a note's address from before folders (``/notes/<slug>``): its id
  .add(
    HttpApiEndpoint.get("legacy", "/legacy/:ref")
      .setPath(Schema.Struct({ ref: Schema.String }))
      .addSuccess(Schema.Struct({ id: NoteId })).addError(NotFound),
  )
  .middleware(Authentication)
{}
