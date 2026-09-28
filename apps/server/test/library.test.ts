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
import { Context, Effect, Either, Layer, Option, Redacted, TestClock } from "effect"
import { randomUUID } from "node:crypto"
import * as Database from "../src/Database.js"
import { ApiLive } from "../src/Http.js"
import { ProviderError, Providers, type OAuthProvider } from "../src/Providers.js"

const databaseUrl = process.env.DATABASE_URL ?? "postgres://postgres:postgres@127.0.0.1:5192/electro"

/** The test schema's address: to open it again (after migrating it only part of the way). */
class SchemaUrl extends Context.Tag("SchemaUrl")<SchemaUrl, string>() {}

/** A schema of its own (the tables, the migrations' record), dropped after the test; ``record``:
 *  which migrations to run (a test of one starts from those before it). */
const schemaWith = (record?: Partial<typeof Database.migrations>) => Layer.unwrapScoped(
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
    return Layer.merge(Database.layer(url.toString(), record), Layer.succeed(SchemaUrl, url.toString()))
  }),
)
const FreshSchema = schemaWith()

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
  Layer.provideMerge(FreshSchema), // the tests may look into the database too
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

const save = (api: Api, document: NotebookDocument, baseRevision: number | null, parentId?: string | null) =>
  api.library.save({ path: { id: document.id }, payload: { document, baseRevision, ...(parentId !== undefined ? { parentId } : {}) } })
const folder = (api: Api, name: string, parentId: string | null = null) => api.library.createFolder({ payload: { name, parentId } })
const open = (api: Api, id: string) => api.library.folder({ path: { id } })
const note = (api: Api, id: string) => api.library.note({ path: { id } })
const patch = (api: Api, id: string, payload: { name?: string; parentId?: string | null }) => api.library.patch({ path: { id }, payload })
const remove = (api: Api, id: string) => api.library.remove({ path: { id } })
type Api = Effect.Effect.Success<ReturnType<typeof signedIn>>

/** A share, straight in the database (sharing has no endpoints yet). */
const share = (item: string, code: string, role: "editor" | "viewer") =>
  Effect.flatMap(SqlClient.SqlClient, (sql) => sql`
    INSERT INTO shares (item_id, user_id, role)
    SELECT ${item}, user_id, ${role} FROM accounts WHERE provider_user_id = ${`google-${code}`}
    ON CONFLICT (item_id, user_id) DO UPDATE SET role = excluded.role`)

describe("notes", () => {
  it.effect("create, read back, on the home screen", () =>
    Effect.gen(function* () {
      const api = yield* signedIn("ala")
      expect(yield* api.library.home()).toEqual([])
      expect(yield* save(api, doc("n1"), null)).toMatchObject({ revision: 1 })
      const [card] = yield* api.library.home()
      expect(card).toMatchObject({ id: "n1", kind: "note", name: "Sprawozdanie", parentId: null, role: "owner", owner: null, count: 0, previews: [] })
      // the first page, for a thumbnail: text, the drawing, the code (it is in the PDF)
      expect(card!.preview).toEqual({ codeInPdf: true, cells: [
        { type: "markdown", source: "# Cel" },
        { type: "schematic", name: "Układ 1", schematic: { elements: [], wires: [] } },
        { type: "code", source: "układ1.solve()" },
      ] })
      const read = yield* note(api, "n1")
      expect(read).toMatchObject({ revision: 1, role: "owner", path: [] })
      expect(read.document).toEqual(doc("n1")) // outputs, results and all: stored as sent
    }).pipe(Effect.provide(TestServer)))

  it.effect("the preview is short, and without code when the PDF has none", () =>
    Effect.gen(function* () {
      const api = yield* signedIn("ala")
      const long = { id: "m", type: "markdown" as const, source: "x".repeat(5000) }
      yield* save(api, { ...doc("n3"), settings: { codeInPdf: false }, cells: [long, ...doc("n3").cells, long] }, null)
      const [card] = yield* api.library.home()
      expect(card!.preview!.cells.map((c) => c.type)).toEqual(["markdown"])
      expect((card!.preview!.cells[0] as { source: string }).source.length).toBe(1600)
    }).pipe(Effect.provide(TestServer)))

  it.effect("keys the contract does not name pass through", () =>
    Effect.gen(function* () {
      const api = yield* signedIn("ala")
      yield* save(api, doc("n2", "X", { tags: ["lab"], settings: { codeInPdf: false, theme: "dark" } }), null)
      expect((yield* note(api, "n2")).document).toMatchObject({ tags: ["lab"], settings: { codeInPdf: false, theme: "dark" } })
    }).pipe(Effect.provide(TestServer)))

  it.effect("saving from the stored revision updates; from an older one is a conflict", () =>
    Effect.gen(function* () {
      const api = yield* signedIn("ala")
      yield* save(api, doc("n1"), null)
      expect((yield* save(api, doc("n1", "Nowy tytuł"), 1)).revision).toBe(2)
      expect(yield* save(api, doc("n1", "Stary"), 1).pipe(Effect.flip)).toMatchObject({ _tag: "RevisionConflict", current: 2, base: 1 })
      expect(yield* save(api, doc("n1"), null).pipe(Effect.flip)).toMatchObject({ _tag: "RevisionConflict", current: 2, base: null })
      expect(yield* save(api, doc("n9"), 3).pipe(Effect.flip)).toMatchObject({ _tag: "RevisionConflict", current: 0, base: 3 })
      expect((yield* note(api, "n1")).document.title).toBe("Nowy tytuł")
    }).pipe(Effect.provide(TestServer)))

  it.effect("missing notes, mismatched ids, delete", () =>
    Effect.gen(function* () {
      const api = yield* signedIn("ala")
      expect(yield* note(api, "nope").pipe(Effect.flip)).toMatchObject({ _tag: "NotFound", id: "nope" })
      const mismatch = yield* api.library.save({ path: { id: "a1" }, payload: { document: doc("b2"), baseRevision: null } }).pipe(Effect.flip)
      expect(mismatch).toMatchObject({ _tag: "NoteIdMismatch", path: "a1", document: "b2" })
      yield* save(api, doc("n1"), null)
      yield* remove(api, "n1")
      expect(yield* api.library.home()).toEqual([])
      expect(yield* remove(api, "n1").pipe(Effect.flip)).toMatchObject({ _tag: "NotFound" })
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

describe("folders", () => {
  it.effect("folders in folders; notes into them; the order; moving, renaming; a folder goes with what is in it", () =>
    Effect.gen(function* () {
      const api = yield* signedIn("ala")
      const lab = yield* folder(api, "Laboratorium")
      const zad = yield* folder(api, "Zadania")
      const pomiary = yield* folder(api, "Pomiary", lab.id)
      yield* save(api, doc("n1", "Mostek"), null, lab.id)
      yield* TestClock.adjust("1 second") // (the test's clock stands still otherwise)
      yield* save(api, doc("n2", "Dzielnik"), null, lab.id)
      yield* save(api, doc("n3", "Luźna"), null)
      // home: folders first (by name), then notes; a folder's card: its notes' first pages, how many things in it
      const home = yield* api.library.home()
      expect(home.map((c) => c.name)).toEqual(["Laboratorium", "Zadania", "Luźna"])
      expect(home[0]).toMatchObject({ kind: "folder", count: 3, role: "owner", preview: null })
      expect(home[0]!.previews).toHaveLength(2)
      // inside: its folders, then its notes (the newest first); the way up
      const inside = yield* open(api, lab.id)
      expect(inside.items.map((c) => c.name)).toEqual(["Pomiary", "Dzielnik", "Mostek"])
      expect((yield* open(api, pomiary.id)).path).toEqual([{ id: lab.id, name: "Laboratorium" }])
      expect((yield* note(api, "n1")).path).toEqual([{ id: lab.id, name: "Laboratorium" }])
      expect(yield* open(api, "n1").pipe(Effect.flip)).toMatchObject({ _tag: "NotFound" }) // a note is not a folder

      // moving: a note into a folder, out to the top; a folder into another
      yield* patch(api, "n3", { parentId: pomiary.id })
      expect((yield* note(api, "n3")).path.map((c) => c.name)).toEqual(["Laboratorium", "Pomiary"])
      yield* patch(api, "n3", { parentId: null })
      yield* patch(api, zad.id, { parentId: pomiary.id })
      expect((yield* open(api, zad.id)).path.map((c) => c.name)).toEqual(["Laboratorium", "Pomiary"])
      // not into itself, nor into a folder inside it; only into a folder
      expect(yield* patch(api, lab.id, { parentId: lab.id }).pipe(Effect.flip)).toMatchObject({ _tag: "MoveIntoItself" })
      expect(yield* patch(api, lab.id, { parentId: zad.id }).pipe(Effect.flip)).toMatchObject({ _tag: "MoveIntoItself" })
      expect(yield* patch(api, "n3", { parentId: "n1" }).pipe(Effect.flip)).toMatchObject({ _tag: "NotAFolder", id: "n1" })
      expect(yield* folder(api, "X", "nope").pipe(Effect.flip)).toMatchObject({ _tag: "NotFound" })

      // renaming: a folder's name; a note's title (a new revision)
      expect((yield* patch(api, lab.id, { name: "Lab" })).name).toBe("Lab")
      expect(yield* patch(api, "n1", { name: "Mostek Wheatstone'a" })).toMatchObject({ name: "Mostek Wheatstone'a" })
      expect(yield* note(api, "n1")).toMatchObject({ revision: 2, document: { title: "Mostek Wheatstone'a" } })
      expect(yield* save(api, doc("n1"), 1).pipe(Effect.flip)).toMatchObject({ _tag: "RevisionConflict", current: 2 })

      // a folder, deleted: what is in it too
      yield* remove(api, lab.id)
      expect((yield* api.library.home()).map((c) => c.name)).toEqual(["Luźna"])
      expect(yield* note(api, "n2").pipe(Effect.flip)).toMatchObject({ _tag: "NotFound" })
    }).pipe(Effect.provide(TestServer)))
})

describe("sharing", () => {
  it.effect("no share: nothing to see, and nothing that says it is there", () =>
    Effect.gen(function* () {
      const ala = yield* signedIn("ala")
      const olek = yield* signedIn("olek")
      const lab = yield* folder(ala, "Laboratorium")
      yield* save(ala, doc("n1", "Mostek"), null, lab.id)
      expect(yield* olek.library.home()).toEqual([])
      const missing = { _tag: "NotFound" }
      expect(yield* open(olek, lab.id).pipe(Effect.flip)).toMatchObject(missing)
      expect(yield* note(olek, "n1").pipe(Effect.flip)).toMatchObject(missing)
      expect(yield* save(olek, doc("n1", "Mostek"), 1).pipe(Effect.flip)).toMatchObject(missing)
      expect(yield* save(olek, doc("n1", "Mostek"), null).pipe(Effect.flip)).toMatchObject(missing) // an id that is taken
      expect(yield* patch(olek, "n1", { name: "X" }).pipe(Effect.flip)).toMatchObject(missing)
      expect(yield* remove(olek, lab.id).pipe(Effect.flip)).toMatchObject(missing)
      expect(yield* folder(olek, "W", lab.id).pipe(Effect.flip)).toMatchObject(missing)
      expect(yield* olek.library.destinations()).toEqual([])
    }).pipe(Effect.provide(TestServer)))

  it.effect("a folder shared to read: on the home screen, all that is in it readable, nothing writable", () =>
    Effect.gen(function* () {
      const ala = yield* signedIn("ala")
      const olek = yield* signedIn("olek")
      const kurs = yield* folder(ala, "Kurs")
      const lab = yield* folder(ala, "Laboratorium", kurs.id)
      yield* save(ala, doc("n1", "Mostek"), null, lab.id)
      yield* share(lab.id, "olek", "viewer")
      const [card] = yield* olek.library.home()
      expect(card).toMatchObject({ id: lab.id, role: "viewer", owner: { name: "ala" } })
      expect((yield* open(olek, lab.id)).items).toMatchObject([{ id: "n1", role: "viewer" }])
      // the way up stops at what was shared: nothing above it shows
      expect(yield* note(olek, "n1")).toMatchObject({ role: "viewer", path: [{ id: lab.id, name: "Laboratorium" }] })
      expect(yield* open(olek, kurs.id).pipe(Effect.flip)).toMatchObject({ _tag: "NotFound" })
      const low = { _tag: "RoleTooLow", needed: "editor", role: "viewer" }
      expect(yield* save(olek, doc("n1", "Nie"), 1).pipe(Effect.flip)).toMatchObject(low)
      expect(yield* save(olek, doc("n5"), null, lab.id).pipe(Effect.flip)).toMatchObject(low)
      expect(yield* folder(olek, "W", lab.id).pipe(Effect.flip)).toMatchObject(low)
      expect(yield* remove(olek, "n1").pipe(Effect.flip)).toMatchObject({ _tag: "RoleTooLow" })
      expect(yield* olek.library.destinations()).toEqual([])
    }).pipe(Effect.provide(TestServer)))

  it.effect("a folder shared to edit: write, make, delete inside — not the folder itself, nor take things out", () =>
    Effect.gen(function* () {
      const ala = yield* signedIn("ala")
      const olek = yield* signedIn("olek")
      const lab = yield* folder(ala, "Laboratorium")
      const sub = yield* folder(ala, "Pomiary", lab.id)
      yield* save(ala, doc("n1", "Mostek"), null, lab.id)
      yield* share(lab.id, "olek", "editor")
      expect((yield* save(olek, doc("n1", "Razem"), 1)).revision).toBe(2)
      expect((yield* note(ala, "n1")).document.title).toBe("Razem")
      // what he makes inside is the folder's owner's
      const his = yield* folder(olek, "Wnioski", lab.id)
      yield* save(olek, doc("n2", "Wnioski Olka"), null, his.id)
      expect((yield* open(ala, his.id)).items.map((c) => c.name)).toEqual(["Wnioski Olka"])
      expect((yield* olek.library.destinations()).map((d) => [d.name, d.parentId]).sort()).toEqual(
        [["Laboratorium", null], ["Pomiary", lab.id], ["Wnioski", lab.id]])
      // moves inside it, deletes inside it
      yield* patch(olek, "n2", { parentId: sub.id })
      yield* remove(olek, his.id)
      // not the shared folder itself; not out into his own things
      expect(yield* remove(olek, lab.id).pipe(Effect.flip)).toMatchObject({ _tag: "RoleTooLow", needed: "owner" })
      const own = yield* folder(olek, "Moje")
      expect(yield* patch(olek, "n1", { parentId: own.id }).pipe(Effect.flip)).toMatchObject({ _tag: "OtherOwner" })
      expect(yield* patch(olek, "n1", { parentId: null }).pipe(Effect.flip)).toMatchObject({ _tag: "OtherOwner" })
      expect(yield* patch(olek, lab.id, { parentId: own.id }).pipe(Effect.flip)).toMatchObject({ _tag: "RoleTooLow" })
    }).pipe(Effect.provide(TestServer)))

  it.effect("one note shared: on the home screen; inside a shared folder: not twice", () =>
    Effect.gen(function* () {
      const ala = yield* signedIn("ala")
      const olek = yield* signedIn("olek")
      const lab = yield* folder(ala, "Laboratorium")
      yield* save(ala, doc("n1", "Mostek"), null, lab.id)
      yield* save(ala, doc("n2", "Sprawozdanie"), null)
      yield* share("n2", "olek", "editor")
      expect((yield* olek.library.home()).map((c) => [c.name, c.role])).toEqual([["Sprawozdanie", "editor"]])
      expect((yield* save(olek, doc("n2", "Wspólne"), 1)).revision).toBe(2)
      expect(yield* remove(olek, "n2").pipe(Effect.flip)).toMatchObject({ _tag: "RoleTooLow" })
      // the folder, and a note in it, both shared: the folder shows; the note is in it (with the better role)
      yield* share(lab.id, "olek", "viewer")
      yield* share("n1", "olek", "editor")
      expect((yield* olek.library.home()).map((c) => c.name)).toEqual(["Laboratorium", "Wspólne"])
      expect((yield* open(olek, lab.id)).items).toMatchObject([{ id: "n1", role: "editor" }])
    }).pipe(Effect.provide(TestServer)))
})

describe("migration 0003: notes into the library", () => {
  it.effect("each user's notes at the top of their own library; ids, revisions and old addresses kept", () =>
    Effect.gen(function* () {
      const url = yield* SchemaUrl
      // the database as it was before folders: two users, their notes (one id in both), an old address
      const users = yield* Effect.gen(function* () {
        const sql = yield* SqlClient.SqlClient
        const [ala] = yield* sql<{ id: string }>`INSERT INTO users (name) VALUES ('ala') RETURNING id`
        const [olek] = yield* sql<{ id: string }>`INSERT INTO users (name) VALUES ('olek') RETURNING id`
        const note = (owner: string, id: string, title: string, slug: string, revision: number, at: string) => sql`
          INSERT INTO notes (owner_id, id, slug, title, document, revision, modified, saved_at, cells, schematics, preview)
          VALUES (${owner}, ${id}, ${slug}, ${title}, ${JSON.stringify(doc(id, title))}, ${revision}, ${at}, ${at}, 3, 1,
                  ${JSON.stringify({ codeInPdf: true, cells: [] })})`
        yield* note(ala!.id, "n1", "Mostek", "mostek", 4, "2026-09-01T10:00:00Z")
        yield* note(ala!.id, "n2", "Dzielnik", "dzielnik", 1, "2026-09-02T10:00:00Z")
        yield* note(olek!.id, "n1", "Moje", "moje", 2, "2026-09-03T10:00:00Z")
        yield* sql`INSERT INTO note_slugs (owner_id, slug, note_id) VALUES (${ala!.id}, 'stary-mostek', 'n1')`
        return { ala: ala!.id, olek: olek!.id }
      }).pipe(Effect.provide(Database.layer(url, { "0001_users": Database.migrations["0001_users"], "0002_notes": Database.migrations["0002_notes"] })))

      const after = yield* Effect.gen(function* () {
        const sql = yield* SqlClient.SqlClient
        const items = yield* sql<{ id: string; owner_id: string; parent_id: string | null; kind: string; name: string; revision: number; document: { id: string } }>`
          SELECT id, owner_id, parent_id, kind, name, revision, document FROM items ORDER BY saved_at`
        const slugs = yield* sql<{ owner_id: string; slug: string; item_id: string }>`SELECT owner_id, slug, item_id FROM legacy_slugs ORDER BY slug`
        const [left] = yield* sql<{ notes: string | null }>`SELECT to_regclass('notes')::text AS notes`
        return { items, slugs, left: left!.notes }
      }).pipe(Effect.provide(Database.layer(url)))

      const [mostek, dzielnik, moje] = after.items
      expect([mostek, dzielnik].map((i) => [i!.id, i!.owner_id, i!.parent_id, i!.kind, i!.name, i!.revision]))
        .toEqual([["n1", users.ala, null, "note", "Mostek", 4], ["n2", users.ala, null, "note", "Dzielnik", 1]])
      // olek's n1 clashed with ala's: a new id, in the document too
      expect(moje).toMatchObject({ owner_id: users.olek, name: "Moje", revision: 2 })
      expect(moje!.id).not.toBe("n1")
      expect(moje!.document.id).toBe(moje!.id)
      expect(after.slugs).toEqual([
        { owner_id: users.ala, slug: "dzielnik", item_id: "n2" },
        { owner_id: users.olek, slug: "moje", item_id: moje!.id },
        { owner_id: users.ala, slug: "mostek", item_id: "n1" },
        { owner_id: users.ala, slug: "stary-mostek", item_id: "n1" },
      ])
      expect(after.left).toBeNull() // the old tables are gone
    }).pipe(Effect.provide(schemaWith({}))))

  it.effect("an address from before folders leads to the note's id", () =>
    Effect.gen(function* () {
      const sql = yield* SqlClient.SqlClient
      const api = yield* signedIn("ala")
      yield* save(api, doc("n1", "Mostek"), null)
      yield* sql`INSERT INTO legacy_slugs (owner_id, slug, item_id)
                 SELECT user_id, 'stary-mostek', 'n1' FROM accounts WHERE provider_user_id = 'google-ala'`
      expect(yield* api.library.legacy({ path: { ref: "stary-mostek" } })).toEqual({ id: "n1" })
      const olek = yield* signedIn("olek") // another user's old address means nothing to him
      expect(yield* olek.library.legacy({ path: { ref: "stary-mostek" } }).pipe(Effect.flip)).toMatchObject({ _tag: "NotFound" })
    }).pipe(Effect.provide(TestServer)))
})

describe("signing in", () => {
  it.effect("without a session: 401 for the notes and for me", () =>
    Effect.gen(function* () {
      const api = yield* client
      expect(yield* api.library.home().pipe(Effect.flip)).toMatchObject({ _tag: "Unauthorized" })
      expect(yield* api.auth.me().pipe(Effect.flip)).toMatchObject({ _tag: "Unauthorized" })
      const forged = yield* HttpApiClient.make(NotesApi, {
        transformClient: HttpClient.mapRequest(HttpClientRequest.setHeader("cookie", "session=made-up")),
      })
      expect(yield* forged.library.home().pipe(Effect.flip)).toMatchObject({ _tag: "Unauthorized" })
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

  it.effect("another provider vouching for the same email: the same user", () =>
    Effect.gen(function* () {
      const google = yield* signedIn("ala")
      yield* save(google, doc("n1"), null)
      const github = yield* signedIn("ala", "github")
      expect((yield* github.library.home()).map((n) => n.id)).toEqual(["n1"])
      expect((yield* github.auth.me()).id).toBe((yield* google.auth.me()).id)
    }).pipe(Effect.provide(TestServer)))
})
