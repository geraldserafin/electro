// The notes server, as atoms: a typed client made from the contract (@electro/notes-api), the
// list of notes as a query, and saving / opening / deleting as mutations. Saving and deleting
// refresh the list through the "notes" reactivity key.
import { Atom, AtomHttpApi } from "@effect-atom/atom-react";
import { FetchHttpClient } from "@effect/platform";
import { NotesApi, type NotebookDocument } from "@electro/notes-api";
import type { Notebook } from "../types";

export class NotesClient extends AtomHttpApi.Tag<NotesClient>()("NotesClient", {
  api: NotesApi,
  httpClient: FetchHttpClient.layer,
  baseUrl: typeof location === "undefined" ? "http://localhost" : location.origin, // /api goes to the server
}) {}

export const NOTES = ["notes"];

/** All notes, newest first (refreshed after every save and delete). */
export const notesAtom = NotesClient.query("notes", "list", { reactivityKeys: NOTES });

export const saveNote = NotesClient.mutation("notes", "save");
export const getNote = NotesClient.mutation("notes", "get");
export const removeNote = NotesClient.mutation("notes", "remove");

/**
 * The same JSON, seen through the contract's type. The notebook's own types are richer (typed
 * results, outputs); the server checks the shape on arrival anyway.
 */
export const toDocument = (notebook: Notebook) => notebook as unknown as NotebookDocument;
export const fromDocument = (document: NotebookDocument) => document as unknown as Notebook;

const LIBRARY_KEY = "electro-library-open";

/** Is the side panel with the notes open (remembered in this browser). */
export const libraryOpenAtom = Atom.writable(
  () => {
    try {
      return localStorage.getItem(LIBRARY_KEY) === "1";
    } catch {
      return false;
    }
  },
  (ctx, open: boolean) => {
    try {
      localStorage.setItem(LIBRARY_KEY, open ? "1" : "0");
    } catch {
      // not remembered — fine
    }
    ctx.setSelf(open);
  },
).pipe(Atom.keepAlive);
