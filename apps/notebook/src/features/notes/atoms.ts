// The notes server, as atoms: a typed client made from the contract (@electro/notes-api), the
// home screen and each folder as queries, and everything that changes them as mutations. A
// change refreshes the queries through the "library" reactivity key.
import { AtomHttpApi } from "@effect-atom/atom-react";
import { FetchHttpClient } from "@effect/platform";
import { NotesApi, slugify, type NotebookDocument } from "@electro/notes-api";
import type { Notebook } from "@/shared/model/types";

export class NotesClient extends AtomHttpApi.Tag<NotesClient>()("NotesClient", {
  api: NotesApi,
  httpClient: FetchHttpClient.layer,
  baseUrl: typeof location === "undefined" ? "http://localhost" : location.origin, // /api goes to the server
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
export const legacyNote = NotesClient.mutation("library", "legacy");

/** Addresses: the id is what counts, the name after it is only for reading. */
export const noteUrl = (id: string, name: string) => `/n/${id}/${slugify(name || "notatka")}`;
export const folderUrl = (id: string, name: string) => `/f/${id}/${slugify(name || "folder")}`;

/**
 * The same JSON, seen through the contract's type. The notebook's own types are richer (typed
 * results, outputs); the server checks the shape on arrival anyway.
 */
export const toDocument = (notebook: Notebook) => notebook as unknown as NotebookDocument;
export const fromDocument = (document: NotebookDocument) => document as unknown as Notebook;
