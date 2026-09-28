/** The HTTP side: the contract's endpoints, implemented with LibraryRepo and Accounts. */
import { HttpApiBuilder, HttpServerResponse } from "@effect/platform"
import type { Cookie } from "@effect/platform/Cookies"
import {
  Authentication, CurrentUser, NoteIdMismatch, NotesApi, ProviderUnavailable, session, Unauthorized, type Provider, type User,
} from "@electro/notes-api"
import * as arctic from "arctic"
import { Config, Effect, Layer, Option, Redacted } from "effect"
import { Accounts, SESSION_DAYS } from "./Accounts.js"
import { ArduinoLive } from "./Arduino.js"
import { LibraryRepo } from "./LibraryRepo.js"
import { Providers } from "./Providers.js"

export const LibraryLive = HttpApiBuilder.group(NotesApi, "library", (handlers) =>
  Effect.gen(function* () {
    const repo = yield* LibraryRepo
    const as = <A, E, R>(f: (user: User) => Effect.Effect<A, E, R>) => Effect.flatMap(CurrentUser, f)
    return handlers
      .handle("home", () => as((u) => repo.home(u.id)))
      .handle("folder", ({ path }) => as((u) => repo.folder(u.id, path.id)))
      .handle("destinations", () => as((u) => repo.destinations(u.id)))
      .handle("createFolder", ({ payload }) => as((u) => repo.createFolder(u.id, payload.name, payload.parentId)))
      .handle("note", ({ path }) => as((u) => repo.note(u.id, path.id)))
      .handle("save", ({ path, payload }) =>
        payload.document.id !== path.id
          ? Effect.fail(new NoteIdMismatch({ path: path.id, document: payload.document.id }))
          : as((u) => repo.save(u.id, payload.document, payload.baseRevision, payload.parentId)))
      .handle("patch", ({ path, payload }) => as((u) => repo.patch(u.id, path.id, payload)))
      .handle("remove", ({ path }) => as((u) => repo.remove(u.id, path.id)))
      .handle("legacy", ({ path }) => as((u) => repo.legacy(u.id, path.ref)))
  }))

/** Only a path on this site: never off to another one after signing in. */
const localPath = (path: string | undefined) =>
  path !== undefined && path.startsWith("/") && !path.startsWith("//") && !path.startsWith("/\\") ? path : "/"

export const AuthLive = HttpApiBuilder.group(NotesApi, "auth", (handlers) =>
  Effect.gen(function* () {
    const accounts = yield* Accounts
    const providers = yield* Providers
    const secure = (yield* Config.string("PUBLIC_URL").pipe(Config.withDefault("http://localhost:5190"))).startsWith("https:")
    // the sign-in's own cookies: from the start to the callback, only for /api/auth
    const flow: Cookie["options"] = { httpOnly: true, secure, sameSite: "lax", path: "/api/auth", maxAge: "10 minutes" }
    const endFlow = (response: HttpServerResponse.HttpServerResponse) =>
      ["oauth_state", "oauth_verifier", "oauth_return"].reduce(
        (r, name) => HttpServerResponse.expireCookie(r, name, { path: "/api/auth" }), response)

    const provider = (name: Provider) =>
      Option.match(Option.fromNullable(providers[name]), {
        onNone: () => Effect.fail(new ProviderUnavailable({ provider: name })),
        onSome: Effect.succeed,
      })

    return handlers
      .handle("providers", () => Effect.succeed(Object.keys(providers) as Array<Provider>))
      .handle("me", () => CurrentUser)
      .handle("logout", ({ request }) =>
        Effect.gen(function* () {
          const token = request.cookies[session.key]
          if (token) yield* accounts.endSession(token)
          return HttpServerResponse.empty({ status: 204 }).pipe(HttpServerResponse.expireCookie(session.key, { path: "/" }))
        }))
      .handle("login", ({ path, urlParams }) =>
        Effect.gen(function* () {
          const oauth = yield* provider(path.provider)
          const state = arctic.generateState()
          const verifier = arctic.generateCodeVerifier()
          return HttpServerResponse.redirect(oauth.authorizationUrl(state, verifier)).pipe(HttpServerResponse.unsafeSetCookies([
            ["oauth_state", state, flow],
            ["oauth_verifier", verifier, flow],
            ["oauth_return", localPath(urlParams.returnTo), flow],
          ]))
        }))
      .handle("callback", ({ path, urlParams, request }) =>
        Effect.gen(function* () {
          const oauth = yield* provider(path.provider)
          const { oauth_state, oauth_verifier = "", oauth_return = "" } = request.cookies
          const { code, state, error } = urlParams
          if (error !== undefined) return endFlow(HttpServerResponse.redirect("/")) // they said no: back to the sign-in page
          if (code === undefined || state === undefined || state !== oauth_state) {
            yield* Effect.logWarning(`Logowanie przez ${path.provider}: brak kodu albo state się nie zgadza`)
            return endFlow(HttpServerResponse.redirect("/?signin=failed"))
          }
          const profile = yield* oauth.profile(code, oauth_verifier)
          const token = yield* accounts.startSession(yield* accounts.signIn(profile))
          return endFlow(HttpServerResponse.redirect(localPath(oauth_return))).pipe(
            HttpServerResponse.unsafeSetCookies([[session.key, token, {
              httpOnly: true, secure, sameSite: "lax", path: "/", maxAge: `${SESSION_DAYS} days`,
            }]]))
        }).pipe(Effect.catchTag("ProviderError", (e) =>
          Effect.logWarning(`Logowanie przez ${path.provider} nie wyszło`, e.cause).pipe(
            Effect.as(endFlow(HttpServerResponse.redirect("/?signin=failed")))))))
  }))

/** A live session in the cookie: its user, as CurrentUser; else 401. */
export const AuthenticationLive = Layer.effect(
  Authentication,
  Effect.gen(function* () {
    const accounts = yield* Accounts
    return Authentication.of({
      session: (token) => accounts.userOf(Redacted.value(token)).pipe(
        Effect.flatMap(Option.match({ onNone: () => Effect.fail(new Unauthorized()), onSome: Effect.succeed })),
      ),
    })
  }),
)

export const SystemLive = HttpApiBuilder.group(NotesApi, "system", (handlers) =>
  handlers.handle("health", () => Effect.succeed({ ok: true as const })))

/** The whole API; needs a database (SqlClient) and the OAuth Providers. */
export const ApiLive = HttpApiBuilder.api(NotesApi).pipe(
  Layer.provide([LibraryLive, AuthLive, SystemLive, ArduinoLive]),
  Layer.provide(AuthenticationLive),
  Layer.provide([LibraryRepo.Default, Accounts.Default]),
)
