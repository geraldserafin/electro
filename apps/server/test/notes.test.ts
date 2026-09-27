// The API end to end: a test HTTP server with an in-memory database, called through a client
// made from the same contract the notebook uses.
import { HttpApiBuilder, HttpApiClient, HttpClient, HttpClientRequest } from "@effect/platform"
import { NodeHttpServer } from "@effect/platform-node"
import { describe, expect, it } from "@effect/vitest"
import { NotesApi, type NotebookDocument } from "@electro/notes-api"
import { Effect, Either, Layer } from "effect"
import * as Database from "../src/Database.js"
import { ApiLive } from "../src/Http.js"

const TestServer = HttpApiBuilder.serve().pipe(
  Layer.provide(ApiLive),
  Layer.provideMerge(NodeHttpServer.layerTest),
  Layer.provide(Database.layer(":memory:")),
)

const client = HttpApiClient.make(NotesApi)

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
      const api = yield* client
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
      const api = yield* client
      const long = { id: "m", type: "markdown" as const, source: "x".repeat(5000) }
      const document = { ...doc("n3"), settings: { codeInPdf: false }, cells: [long, ...doc("n3").cells, long] }
      yield* api.notes.save({ path: { id: "n3" }, payload: { document, baseRevision: null } })
      const [summary] = yield* api.notes.list()
      expect(summary!.preview.cells.map((c) => c.type)).toEqual(["markdown"])
      expect((summary!.preview.cells[0] as { source: string }).source.length).toBe(1600)
    }).pipe(Effect.provide(TestServer)))

  it.effect("addresses: a slug from the title, unique; old slugs and the id keep working", () =>
    Effect.gen(function* () {
      const api = yield* client
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
      const api = yield* client
      const document = doc("n2", "X", { tags: ["lab"], settings: { codeInPdf: false, theme: "dark" } })
      yield* api.notes.save({ path: { id: "n2" }, payload: { document, baseRevision: null } })
      const back = (yield* api.notes.get({ path: { ref: "n2" } })).document
      expect(back).toMatchObject({ tags: ["lab"], settings: { codeInPdf: false, theme: "dark" } })
    }).pipe(Effect.provide(TestServer)))

  it.effect("saving from the stored revision updates; from an older one is a conflict", () =>
    Effect.gen(function* () {
      const api = yield* client
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
      const api = yield* client
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
      const bad = (payload: unknown) => HttpClientRequest.put("/api/notes/x").pipe(
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
