// The API end to end: a test HTTP server on a fresh Postgres schema (one per test, in the
// database at DATABASE_URL: devenv's), called through a client made from the same contract the
// notebook uses. Signing in goes the whole way (the redirect, the callback), with a stand-in for
// the provider.
import { HttpApiBuilder, HttpApiClient, HttpClient, HttpClientRequest, HttpClientResponse } from "@effect/platform"
import * as Cookies from "@effect/platform/Cookies"
import { NodeHttpServer } from "@effect/platform-node"
import { SqlClient } from "@effect/sql"
import { PgClient } from "@effect/sql-pg"
import { describe, expect, it } from "@effect/vitest"
import { NotesApi, type NotebookDocument } from "@electro/notes-api"
import { Effect, Either, Layer, Option, Redacted } from "effect"
import { randomUUID } from "node:crypto"
import * as Database from "../src/Database.js"
import { ApiLive } from "../src/Http.js"
import { ProviderError, Providers, type OAuthProvider } from "../src/Providers.js"

const databaseUrl = process.env.DATABASE_URL ?? "postgres://postgres:postgres@127.0.0.1:5192/electro"

/** A schema of its own (the tables, the migrations' record), dropped after the test. */
const FreshSchema = Layer.unwrapScoped(
  Effect.gen(function* () {
    const schema = `test_${randomUUID().replaceAll("-", "")}`
    const admin = (make: (sql: SqlClient.SqlClient) => Effect.Effect<unknown, unknown>) =>
      Effect.flatMap(SqlClient.SqlClient, make).pipe(Effect.provide(PgClient.layer({ url: Redacted.make(databaseUrl) })), Effect.orDie)
    yield* Effect.acquireRelease(
      admin((sql) => sql`CREATE SCHEMA ${sql(schema)}`),
      () => admin((sql) => sql`DROP SCHEMA ${sql(schema)} CASCADE`),
    )
    const url = new URL(databaseUrl)
    url.searchParams.set("options", `-c search_path=${schema}`)
    return Database.layer(url.toString())
  }),
)

/** A provider that signs in whoever the code names ("bad": the provider refuses). */
const standIn = (provider: "google" | "github", verified = true): OAuthProvider => ({
  authorizationUrl: (state) => new URL(`https://${provider}.test/consent?state=${state}`),
  profile: (code) => code === "bad"
    ? Effect.fail(new ProviderError({ cause: "invalid_grant" }))
    : Effect.succeed({ provider, id: `${provider}-${code}`, name: code, email: verified ? `${code}@example.com` : null, avatarUrl: null }),
})

const TestServer = HttpApiBuilder.serve().pipe(
  Layer.provide(ApiLive),
  Layer.provide(Layer.succeed(Providers, { google: standIn("google"), github: standIn("github") })),
  Layer.provideMerge(NodeHttpServer.layerTest),
  Layer.provide(FreshSchema),
)

/** Signing in with `provider` as `code` says: the callback's response (a redirect, the session cookie). */
const signInResponse = (code: string, { provider = "google", returnTo = "/", state }: { provider?: string; returnTo?: string; state?: string } = {}) =>
  Effect.gen(function* () {
    const http = yield* HttpClient.HttpClient
    const start = yield* http.get(`/api/auth/${provider}`, { urlParams: { returnTo } })
    expect(start.status).toBe(302)
    const consent = new URL(start.headers.location!)
    return yield* HttpClientRequest.get(`/api/auth/${provider}/callback`).pipe(
      HttpClientRequest.setUrlParams({ code, state: state ?? consent.searchParams.get("state")! }),
      HttpClientRequest.setHeader("cookie", Cookies.toCookieHeader(start.cookies)),
      http.execute,
    )
  })

/** A client signed in as `code` says (the same code: the same user). */
const signedIn = (code: string, provider = "google") =>
  Effect.gen(function* () {
    const token = Cookies.toRecord((yield* signInResponse(code, { provider })).cookies).session
    expect(token).toBeDefined()
    return yield* HttpApiClient.make(NotesApi, {
      transformClient: HttpClient.mapRequest(HttpClientRequest.setHeader("cookie", `session=${token}`)),
    })
  })

const client = HttpApiClient.make(NotesApi) // no one signed in

const doc = (id: string, title = "Sprawozdanie", extra: Record<string, unknown> = {}): NotebookDocument => ({
  format: "electro-notebook", version: 2, id, title, created: "2026-09-27T10:00:00Z", modified: "2026-09-27T10:00:00Z",
  settings: { codeInPdf: true },
  cells: [
    { id: "a", type: "markdown", source: "# Cel" },
    { id: "b", type: "schematic", name: "Układ 1", schematic: { elements: [], wires: [] }, results: { R_1: { value: "3 Ω" } } },
    { id: "c", type: "code", source: "układ1.solve()", outputs: [{ type: "text", data: "E = 54 V" }] },
  ],
  ...extra,
})

describe("notes API", () => {
  it.effect("create, list, read back", () =>
    Effect.gen(function* () {
      const api = yield* signedIn("ala")
      expect(yield* api.notes.list()).toEqual([])
      const saved = yield* api.notes.save({ path: { id: "n1" }, payload: { document: doc("n1"), baseRevision: null } })
      expect(saved.revision).toBe(1)
      const [summary] = yield* api.notes.list()
      expect(summary).toMatchObject({ id: "n1", title: "Sprawozdanie", revision: 1, cells: 3, schematics: 1 })
      // the first page, for a thumbnail: text, the drawing, the code (it is in the PDF)
      expect(summary!.preview).toEqual({ codeInPdf: true, cells: [
        { type: "markdown", source: "# Cel" },
        { type: "schematic", name: "Układ 1", schematic: { elements: [], wires: [] } },
        { type: "code", source: "układ1.solve()" },
      ] })
      const note = yield* api.notes.get({ path: { ref: "n1" } })
      expect(note.revision).toBe(1)
      expect(note.document).toEqual(doc("n1")) // outputs, results and all: stored as sent
    }).pipe(Effect.provide(TestServer)))

  it.effect("the preview is short, and without code when the PDF has none", () =>
    Effect.gen(function* () {
      const api = yield* signedIn("ala")
      const long = { id: "m", type: "markdown" as const, source: "x".repeat(5000) }
      const document = { ...doc("n3"), settings: { codeInPdf: false }, cells: [long, ...doc("n3").cells, long] }
      yield* api.notes.save({ path: { id: "n3" }, payload: { document, baseRevision: null } })
      const [summary] = yield* api.notes.list()
      expect(summary!.preview.cells.map((c) => c.type)).toEqual(["markdown"])
      expect((summary!.preview.cells[0] as { source: string }).source.length).toBe(1600)
    }).pipe(Effect.provide(TestServer)))

  it.effect("addresses: a slug from the title, unique; old slugs and the id keep working", () =>
    Effect.gen(function* () {
      const api = yield* signedIn("ala")
      const a = yield* api.notes.save({ path: { id: "a" }, payload: { document: doc("a", "Zadanie 4 — mostek Wheatstone'a"), baseRevision: null } })
      expect(a.slug).toBe("zadanie-4-mostek-wheatstonea")
      const b = yield* api.notes.save({ path: { id: "b" }, payload: { document: doc("b", "Zadanie 4: mostek Wheatstone’a!"), baseRevision: null } })
      expect(b.slug).toBe("zadanie-4-mostek-wheatstonea-2") // the same title: a suffix
      expect((yield* api.notes.save({ path: { id: "b" }, payload: { document: doc("b", "Zadanie 4 – mostek Wheatstone'a"), baseRevision: 1 } })).slug)
        .toBe("zadanie-4-mostek-wheatstonea-2") // a title that still makes it: the address stays
      const renamed = yield* api.notes.save({ path: { id: "a" }, payload: { document: doc("a", "Łączenie źródeł"), baseRevision: 1 } })
      expect(renamed.slug).toBe("laczenie-zrodel")
      for (const ref of ["laczenie-zrodel", "zadanie-4-mostek-wheatstonea", "a"]) // new, old, id
        expect((yield* api.notes.get({ path: { ref } })).document.id).toBe("a")
      // an old slug is not handed to another note
      const c = yield* api.notes.save({ path: { id: "c" }, payload: { document: doc("c", "Zadanie 4 — mostek Wheatstone'a"), baseRevision: null } })
      expect(c.slug).toBe("zadanie-4-mostek-wheatstonea-3")
      expect((yield* api.notes.list()).map((n) => n.slug).sort()).toEqual(
        ["laczenie-zrodel", "zadanie-4-mostek-wheatstonea-2", "zadanie-4-mostek-wheatstonea-3"])
      // deleted: its addresses are free again
      yield* api.notes.remove({ path: { id: "a" } })
      expect(yield* api.notes.get({ path: { ref: "laczenie-zrodel" } }).pipe(Effect.flip)).toMatchObject({ _tag: "NoteNotFound" })
      const d = yield* api.notes.save({ path: { id: "d" }, payload: { document: doc("d", "Łączenie źródeł"), baseRevision: null } })
      expect(d.slug).toBe("laczenie-zrodel")
    }).pipe(Effect.provide(TestServer)))

  it.effect("keys the contract does not name pass through", () =>
    Effect.gen(function* () {
      const api = yield* signedIn("ala")
      const document = doc("n2", "X", { tags: ["lab"], settings: { codeInPdf: false, theme: "dark" } })
      yield* api.notes.save({ path: { id: "n2" }, payload: { document, baseRevision: null } })
      const back = (yield* api.notes.get({ path: { ref: "n2" } })).document
      expect(back).toMatchObject({ tags: ["lab"], settings: { codeInPdf: false, theme: "dark" } })
    }).pipe(Effect.provide(TestServer)))

  it.effect("saving from the stored revision updates; from an older one is a conflict", () =>
    Effect.gen(function* () {
      const api = yield* signedIn("ala")
      yield* api.notes.save({ path: { id: "n1" }, payload: { document: doc("n1"), baseRevision: null } })
      const second = yield* api.notes.save({ path: { id: "n1" }, payload: { document: doc("n1", "Nowy tytuł"), baseRevision: 1 } })
      expect(second.revision).toBe(2)
      // another tab still at revision 1
      const stale = yield* api.notes.save({ path: { id: "n1" }, payload: { document: doc("n1", "Stary"), baseRevision: 1 } }).pipe(Effect.flip)
      expect(stale).toMatchObject({ _tag: "RevisionConflict", current: 2, base: 1 })
      // creating what exists
      const again = yield* api.notes.save({ path: { id: "n1" }, payload: { document: doc("n1"), baseRevision: null } }).pipe(Effect.flip)
      expect(again).toMatchObject({ _tag: "RevisionConflict", current: 2, base: null })
      // updating what does not exist
      const ghost = yield* api.notes.save({ path: { id: "n9" }, payload: { document: doc("n9"), baseRevision: 3 } }).pipe(Effect.flip)
      expect(ghost).toMatchObject({ _tag: "RevisionConflict", current: 0, base: 3 })
      expect((yield* api.notes.get({ path: { ref: "n1" } })).document.title).toBe("Nowy tytuł")
    }).pipe(Effect.provide(TestServer)))

  it.effect("missing notes, mismatched ids, delete", () =>
    Effect.gen(function* () {
      const api = yield* signedIn("ala")
      expect(yield* api.notes.get({ path: { ref: "nope" } }).pipe(Effect.flip)).toMatchObject({ _tag: "NoteNotFound", id: "nope" })
      const mismatch = yield* api.notes.save({ path: { id: "a1" }, payload: { document: doc("b2"), baseRevision: null } }).pipe(Effect.flip)
      expect(mismatch).toMatchObject({ _tag: "NoteIdMismatch", path: "a1", document: "b2" })
      yield* api.notes.save({ path: { id: "n1" }, payload: { document: doc("n1"), baseRevision: null } })
      yield* api.notes.remove({ path: { id: "n1" } })
      expect(yield* api.notes.list()).toEqual([])
      expect(yield* api.notes.remove({ path: { id: "n1" } }).pipe(Effect.flip)).toMatchObject({ _tag: "NoteNotFound" })
    }).pipe(Effect.provide(TestServer)))

  it.effect("a document that is not a notebook is rejected with 400", () =>
    Effect.gen(function* () {
      const http = yield* HttpClient.HttpClient
      const done = yield* signInResponse("ala")
      const bad = (payload: unknown) => HttpClientRequest.put("/api/notes/x").pipe(
        HttpClientRequest.setHeader("cookie", `session=${Cookies.toRecord(done.cookies).session}`),
        HttpClientRequest.bodyUnsafeJson(payload),
        http.execute,
        Effect.map((r) => r.status),
      )
      expect(yield* bad({ document: { ...doc("x"), version: 1 }, baseRevision: null })).toBe(400)
      expect(yield* bad({ document: { ...doc("x"), cells: [{ id: "a", type: "wideo" }] }, baseRevision: null })).toBe(400)
      expect(yield* bad({ document: doc("x") })).toBe(400) // no baseRevision
      expect(Either.isRight(yield* Effect.either((yield* client).system.health()))).toBe(true)
    }).pipe(Effect.provide(TestServer)))
})

describe("signing in", () => {
  it.effect("without a session: 401 for the notes and for me", () =>
    Effect.gen(function* () {
      const api = yield* client
      expect(yield* api.notes.list().pipe(Effect.flip)).toMatchObject({ _tag: "Unauthorized" })
      expect(yield* api.auth.me().pipe(Effect.flip)).toMatchObject({ _tag: "Unauthorized" })
      const forged = yield* HttpApiClient.make(NotesApi, {
        transformClient: HttpClient.mapRequest(HttpClientRequest.setHeader("cookie", "session=made-up")),
      })
      expect(yield* forged.notes.list().pipe(Effect.flip)).toMatchObject({ _tag: "Unauthorized" })
    }).pipe(Effect.provide(TestServer)))

  it.effect("the providers set up; one that is not: 404", () =>
    Effect.gen(function* () {
      expect([...yield* (yield* client).auth.providers()].sort()).toEqual(["github", "google"])
      const http = yield* HttpClient.HttpClient
      expect((yield* http.get("/api/auth/microsoft")).status).toBe(404)
    }).pipe(Effect.provide(TestServer)))

  it.effect("the callback: a session, back where the sign-in started (only a path here)", () =>
    Effect.gen(function* () {
      const done = yield* signInResponse("ala", { returnTo: "/notes/mostek?x=1" })
      expect(done.status).toBe(302)
      expect(done.headers.location).toBe("/notes/mostek?x=1")
      const session = Cookies.get(done.cookies, "session")
      expect(Option.getOrThrow(session).options).toMatchObject({ httpOnly: true, sameSite: "lax", path: "/" }) // out of the page's JavaScript
      for (const elsewhere of ["//evil.test/x", "https://evil.test", "/\\evil.test"])
        expect((yield* signInResponse("ala", { returnTo: elsewhere })).headers.location).toBe("/")
    }).pipe(Effect.provide(TestServer)))

  it.effect("a callback that does not match the start, or a code the provider refuses: no session", () =>
    Effect.gen(function* () {
      for (const done of [yield* signInResponse("ala", { state: "someone-elses" }), yield* signInResponse("bad")]) {
        expect(done.headers.location).toBe("/?signin=failed")
        expect(Cookies.toRecord(done.cookies).session).toBeUndefined()
      }
    }).pipe(Effect.provide(TestServer)))

  it.effect("me, and signing out ends the session", () =>
    Effect.gen(function* () {
      const api = yield* signedIn("ala")
      expect(yield* api.auth.me()).toMatchObject({ name: "ala", email: "ala@example.com" })
      yield* api.auth.logout()
      expect(yield* api.auth.me().pipe(Effect.flip)).toMatchObject({ _tag: "Unauthorized" })
    }).pipe(Effect.provide(TestServer)))

  it.effect("each user's notes are their own: not listed, read, deleted or overwritten by another", () =>
    Effect.gen(function* () {
      const ala = yield* signedIn("ala")
      const olek = yield* signedIn("olek")
      yield* ala.notes.save({ path: { id: "n1" }, payload: { document: doc("n1", "Mostek"), baseRevision: null } })
      expect(yield* olek.notes.list()).toEqual([])
      expect(yield* olek.notes.get({ path: { ref: "n1" } }).pipe(Effect.flip)).toMatchObject({ _tag: "NoteNotFound" })
      expect(yield* olek.notes.get({ path: { ref: "mostek" } }).pipe(Effect.flip)).toMatchObject({ _tag: "NoteNotFound" })
      expect(yield* olek.notes.remove({ path: { id: "n1" } }).pipe(Effect.flip)).toMatchObject({ _tag: "NoteNotFound" })
      // the same id and title: his own note, at the same address
      const his = yield* olek.notes.save({ path: { id: "n1" }, payload: { document: doc("n1", "Mostek", { tags: ["olek"] }), baseRevision: null } })
      expect(his).toMatchObject({ revision: 1, slug: "mostek" })
      expect((yield* ala.notes.get({ path: { ref: "mostek" } })).document).toEqual(doc("n1", "Mostek"))
    }).pipe(Effect.provide(TestServer)))

  it.effect("another provider vouching for the same email: the same user", () =>
    Effect.gen(function* () {
      const google = yield* signedIn("ala")
      yield* google.notes.save({ path: { id: "n1" }, payload: { document: doc("n1"), baseRevision: null } })
      const github = yield* signedIn("ala", "github")
      expect((yield* github.notes.list()).map((n) => n.id)).toEqual(["n1"])
      expect((yield* github.auth.me()).id).toBe((yield* google.auth.me()).id)
    }).pipe(Effect.provide(TestServer)))
})
