/**
 * Who is asking: a user signs in with an OAuth provider (Google, GitHub, Microsoft) and gets a
 * session, kept in an httpOnly cookie. Endpoints behind Authentication see the user as
 * CurrentUser; without a live session they answer 401.
 */
import { HttpApiEndpoint, HttpApiGroup, HttpApiMiddleware, HttpApiSchema, HttpApiSecurity } from "@effect/platform"
import { Context, Schema } from "effect"

export const UserId = Schema.String.pipe(Schema.brand("UserId"))
export type UserId = typeof UserId.Type

export class User extends Schema.Class<User>("User")({
  id: UserId,
  name: Schema.String,
  email: Schema.NullOr(Schema.String), // only a verified one; null when the provider does not vouch for it
  avatarUrl: Schema.NullOr(Schema.String),
}) {}

export const Provider = Schema.Literal("google", "github", "microsoft")
export type Provider = typeof Provider.Type

export class Unauthorized extends Schema.TaggedError<Unauthorized>()(
  "Unauthorized",
  {},
  HttpApiSchema.annotations({ status: 401 }),
) {
  get message() {
    return "Not signed in (no session, or it expired)."
  }
}

/** The server has no OAuth app for this provider (no client id and secret configured). */
export class ProviderUnavailable extends Schema.TaggedError<ProviderUnavailable>()(
  "ProviderUnavailable",
  { provider: Provider },
  HttpApiSchema.annotations({ status: 404 }),
) {
  get message() {
    return `Signing in with ${this.provider} is not set up on this server.`
  }
}

/** The signed-in user, for the handlers behind Authentication. */
export class CurrentUser extends Context.Tag("CurrentUser")<CurrentUser, User>() {}

/** The session cookie. */
export const session = HttpApiSecurity.apiKey({ in: "cookie", key: "session" })

export class Authentication extends HttpApiMiddleware.Tag<Authentication>()("Authentication", {
  failure: Unauthorized,
  provides: CurrentUser,
  security: { session },
}) {}

const ByProvider = Schema.Struct({ provider: Provider })

export class AuthGroup extends HttpApiGroup.make("auth")
  .add(
    // the providers this server can sign in with (the sign-in page's buttons)
    HttpApiEndpoint.get("providers", "/auth/providers")
      .addSuccess(Schema.Array(Provider)),
  )
  .add(
    HttpApiEndpoint.get("me", "/auth/me")
      .addSuccess(User)
      .middleware(Authentication),
  )
  .add(
    HttpApiEndpoint.post("logout", "/auth/logout")
      .addSuccess(Schema.Void),
  )
  .add(
    // a link, not a call: off to the provider's consent screen; back to returnTo (a path here) after
    HttpApiEndpoint.get("login", "/auth/:provider")
      .setPath(ByProvider)
      .setUrlParams(Schema.Struct({ returnTo: Schema.optional(Schema.String) }))
      .addSuccess(Schema.Void, { status: 302 })
      .addError(ProviderUnavailable),
  )
  .add(
    // where the provider sends the browser back: a session, then returnTo (or /?signin=failed)
    HttpApiEndpoint.get("callback", "/auth/:provider/callback")
      .setPath(ByProvider)
      .setUrlParams(Schema.Struct({
        code: Schema.optional(Schema.String),
        state: Schema.optional(Schema.String),
        error: Schema.optional(Schema.String), // e.g. access_denied: the user said no
      }))
      .addSuccess(Schema.Void, { status: 302 })
      .addError(ProviderUnavailable),
  )
{}
