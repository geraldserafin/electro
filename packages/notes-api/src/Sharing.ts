/**
 * Sharing an item (a note, or a folder with everything in it): with people by their email (they
 * must have signed in here before), or with anyone who has its link — opening it adds them, with
 * the link's role. Only the item's owner sees and changes who has it; someone it was shared with
 * may leave (it goes from their home screen; the link would bring it back).
 *
 * An item has at most one link; a new one makes the old one stop working.
 */
import { HttpApiEndpoint, HttpApiGroup, HttpApiSchema } from "@effect/platform"
import { Schema } from "effect"
import { Authentication, UserId } from "./Auth.js"
import { ItemKind, NotFound, Person, RoleTooLow } from "./Library.js"
import { NoteId } from "./Notebook.js"

/** What a share lets do: an owner is only ever the owner. */
export const ShareRole = Schema.Literal("editor", "viewer")
export type ShareRole = typeof ShareRole.Type

export const Member = Schema.Struct({
  id: UserId,
  name: Schema.String,
  email: Schema.NullOr(Schema.String),
  avatarUrl: Schema.NullOr(Schema.String),
  role: ShareRole,
}).annotations({ identifier: "Member" })
export type Member = typeof Member.Type

export const ShareLink = Schema.Struct({ token: Schema.String, role: ShareRole })
export type ShareLink = typeof ShareLink.Type

/** Who has the item: its owner, the people it was shared with, its link. */
export const Sharing = Schema.Struct({
  owner: Person,
  people: Schema.Array(Member),
  link: Schema.NullOr(ShareLink),
}).annotations({ identifier: "Sharing" })
export type Sharing = typeof Sharing.Type

/** Where a link led: the item, now the user's to open. */
export const Joined = Schema.Struct({ id: NoteId, kind: ItemKind, name: Schema.String })
export type Joined = typeof Joined.Type

/** No one with this email has signed in here. */
export class NoSuchPerson extends Schema.TaggedError<NoSuchPerson>()(
  "NoSuchPerson",
  { email: Schema.String },
  HttpApiSchema.annotations({ status: 404 }),
) {
  get message() {
    return `No one with ${this.email} has signed in yet.`
  }
}

const ById = Schema.Struct({ id: NoteId })
const Email = Schema.Trim.pipe(Schema.minLength(3), Schema.maxLength(320))

export class SharingGroup extends HttpApiGroup.make("sharing")
  .add(HttpApiEndpoint.get("get", "/items/:id/sharing").setPath(ById).addSuccess(Sharing).addError(NotFound).addError(RoleTooLow))
  .add(
    HttpApiEndpoint.post("add", "/items/:id/people")
      .setPath(ById).setPayload(Schema.Struct({ email: Email, role: ShareRole }))
      .addSuccess(Sharing).addError(NotFound).addError(RoleTooLow).addError(NoSuchPerson),
  )
  .add(
    HttpApiEndpoint.put("setRole", "/items/:id/people/:user")
      .setPath(Schema.Struct({ id: NoteId, user: UserId })).setPayload(Schema.Struct({ role: ShareRole }))
      .addSuccess(Sharing).addError(NotFound).addError(RoleTooLow),
  )
  .add(
    HttpApiEndpoint.del("unshare", "/items/:id/people/:user")
      .setPath(Schema.Struct({ id: NoteId, user: UserId }))
      .addSuccess(Sharing).addError(NotFound).addError(RoleTooLow),
  )
  // the item shared with the user: off their home screen, not theirs any more
  .add(HttpApiEndpoint.post("leave", "/items/:id/leave").setPath(ById).addSuccess(Schema.Void).addError(NotFound))
  // the link: made (or its role changed), made anew (the old one stops working), taken away
  .add(
    HttpApiEndpoint.put("link", "/items/:id/link")
      .setPath(ById).setPayload(Schema.Struct({ role: ShareRole }))
      .addSuccess(Sharing).addError(NotFound).addError(RoleTooLow),
  )
  .add(HttpApiEndpoint.post("newLink", "/items/:id/link/new").setPath(ById).addSuccess(Sharing).addError(NotFound).addError(RoleTooLow))
  .add(HttpApiEndpoint.del("unlink", "/items/:id/link").setPath(ById).addSuccess(Sharing).addError(NotFound).addError(RoleTooLow))
  .add(
    HttpApiEndpoint.post("join", "/join/:token")
      .setPath(Schema.Struct({ token: Schema.String })).addSuccess(Joined).addError(NotFound),
  )
  .middleware(Authentication)
{}
