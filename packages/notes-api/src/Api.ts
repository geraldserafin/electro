/**
 * The notes API: the one description of the endpoints, used by the server (to implement them)
 * and by the notebook (to call them, with typed results and errors). Notes live in folders
 * (Library.ts), seen by their owner and whoever they are shared with (Sharing.ts); without a session those
 * endpoints answer 401.
 */
import { HttpApi, HttpApiEndpoint, HttpApiGroup } from "@effect/platform"
import { Schema } from "effect"
import { ArduinoGroup } from "./Arduino.js"
import { AuthGroup } from "./Auth.js"
import { LibraryGroup } from "./Library.js"
import { SharingGroup } from "./Sharing.js"

export class SystemGroup extends HttpApiGroup.make("system")
  .add(HttpApiEndpoint.get("health", "/health").addSuccess(Schema.Struct({ ok: Schema.Literal(true) })))
{}

export class NotesApi extends HttpApi.make("notes")
  .add(LibraryGroup)
  .add(SharingGroup)
  .add(AuthGroup)
  .add(SystemGroup)
  .add(ArduinoGroup)
  .prefix("/api")
{}
