// The notes, as atoms: a typed client made from the contract (@electro/notes-api), answered in the
// page from the user's vault on GitHub (features/vault); the home screen and each folder as
// queries, and everything that changes them as mutations. A change refreshes the queries through
// the "library" reactivity key.

import { FetchHttpClient, HttpClient } from "@effect/platform";
import { AtomHttpApi } from "@effect-atom/atom-react";
import { type NotebookDocument, NotesApi, slugify } from "@electro/notes-api";
import { Effect, Layer } from "effect";
import { apiFetch } from "@/features/vault";
import type { Notebook } from "@/shared/model/types";

export class NotesClient extends AtomHttpApi.Tag<NotesClient>()("NotesClient", {
  api: NotesApi,
  // (fetch: the one the vault answers)
  httpClient: Layer.effect(
    HttpClient.HttpClient,
    Effect.map(
      HttpClient.HttpClient,
      HttpClient.transform((request) => Effect.provideService(request, FetchHttpClient.Fetch, apiFetch)),
    ),
  ).pipe(Layer.provide(FetchHttpClient.layer)),
  baseUrl: typeof location === "undefined" ? "http://localhost" : location.origin,
}) {}

/** What any change makes stale: the home screen, every folder, the destinations. */
export const LIBRARY = ["library"];

/** The top: the user's own folders and notes, and what others shared with them. */
export const homeAtom = NotesClient.query("library", "home", { reactivityKeys: LIBRARY });

/** Every folder the user may put things into ("Move to…"). */
export const destinationsAtom = NotesClient.query("library", "destinations", { reactivityKeys: LIBRARY });

const folderQuery = (id: string) => NotesClient.query("library", "folder", { path: { id }, reactivityKeys: LIBRARY });
const folders = new Map<string, ReturnType<typeof folderQuery>>();
/** A folder: itself, the way up to it, what is in it. */
export const folderAtom = (id: string) => {
  let atom = folders.get(id);
  if (!atom) folders.set(id, (atom = folderQuery(id)));
  return atom;
};

export const getNote = NotesClient.mutation("library", "note");
export const saveNote = NotesClient.mutation("library", "save");
export const createFolder = NotesClient.mutation("library", "createFolder");
export const patchItem = NotesClient.mutation("library", "patch");
export const removeItem = NotesClient.mutation("library", "remove");

/** The lists read again (after a sync brought GitHub's changes): a call that changes nothing, with the
 *  library's reactivity key. */
export const refreshLibrary = NotesClient.mutation("system", "health");

/** Addresses: the id is what counts, the name after it is only for reading. */
export const noteUrl = (id: string, name: string) => `/n/${id}/${slugify(name || "notatka")}`;
export const folderUrl = (id: string, name: string) => `/f/${id}/${slugify(name || "folder")}`;

/**
 * The same JSON, seen through the contract's type. The notebook's own types are richer (typed
 * results, outputs); the server checks the shape on arrival anyway.
 */
export const toDocument = (notebook: Notebook) => notebook as unknown as NotebookDocument;
export const fromDocument = (document: NotebookDocument) => document as unknown as Notebook;
