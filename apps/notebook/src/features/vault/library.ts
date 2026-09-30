/**
 * The library as the vault keeps it: library.json says where things are — each folder (its name, the
 * folder it is in) and each note (its folder) — and each note is a file of its own, notes/<id>.json,
 * its document; a note's name is its title. So editing a note touches only its file, and two places
 * that edited different notes join without a fuss (merge.ts). Everything is the user's: their role
 * is always owner, and nothing is shared.
 *
 * What the notes server's LibraryRepo did, over these files: reading gives the cards, changing gives
 * the library anew (and the error, when there is one, is the contract's).
 */
import {
  type Crumb,
  type Destination,
  type Folder,
  type ItemCard,
  MoveIntoItself,
  NotAFolder,
  type NotePreview,
  NotFound,
} from "@electro/notes-api";

export interface Library {
  readonly version: 2;
  readonly folders: Readonly<
    Record<string, { readonly name: string; readonly parentId: string | null; readonly created: string }>
  >;
  readonly notes: Readonly<Record<string, { readonly parentId: string | null }>>;
}

/** What a note's card shows, from its document. */
export interface NoteInfo {
  readonly title: string;
  readonly modified: string;
  readonly preview: NotePreview;
}

/** The library and the notes it has. */
export interface State {
  readonly library: Library;
  readonly notes: ReadonlyMap<string, NoteInfo>;
}

export const empty: Library = { version: 2, folders: {}, notes: {} };

export const notePath = (id: string) => `notes/${id}.json`;

/** The library as it must be for the notes there are: every note in it (a new one at the top),
 *  nothing in a folder that is not there any more. */
export function normalize(library: Library, notes: Iterable<string>): Library {
  const ids = new Set(notes);
  const up = (parentId: string | null) => (parentId !== null && library.folders[parentId] ? parentId : null);
  return {
    version: 2,
    folders: Object.fromEntries(
      Object.entries(library.folders).map(([id, f]) => [id, { ...f, parentId: up(f.parentId) }]),
    ),
    notes: Object.fromEntries([...ids].map((id) => [id, { parentId: up(library.notes[id]?.parentId ?? null) }])),
  };
}

/** Two libraries that went on from ``base``, joined: each folder's and note's place from the side
 *  that changed it (both did: ours). */
export function mergeLibraries(base: Library, ours: Library, theirs: Library): Library {
  const join = <V>(b: Readonly<Record<string, V>>, o: Readonly<Record<string, V>>, t: Readonly<Record<string, V>>) => {
    const out: Record<string, V> = {};
    for (const key of new Set([...Object.keys(o), ...Object.keys(t)])) {
      const same = (x: V | undefined, y: V | undefined) => JSON.stringify(x) === JSON.stringify(y);
      const value = same(o[key], b[key]) ? t[key] : o[key];
      if (value !== undefined) out[key] = value;
    }
    return out;
  };
  return {
    version: 2,
    folders: join(base.folders ?? {}, ours.folders, theirs.folders ?? {}),
    notes: join(base.notes ?? {}, ours.notes, theirs.notes ?? {}),
  };
}

// ------------------------------------------------------------------ cards

type Item = { id: string; kind: "folder" | "note"; name: string; parentId: string | null; at: string };

function items({ library, notes }: State): Item[] {
  return [
    ...Object.entries(library.folders).map(([id, f]) => ({
      id,
      kind: "folder" as const,
      name: f.name,
      parentId: f.parentId,
      at: f.created,
    })),
    ...Object.entries(library.notes).flatMap(([id, n]) => {
      const info = notes.get(id);
      return info ? [{ id, kind: "note" as const, name: info.title, parentId: n.parentId, at: info.modified }] : [];
    }),
  ];
}

/** Folders first (by name), then notes (the newest first). */
const order = (x: Item, y: Item) =>
  x.kind !== y.kind
    ? x.kind === "folder"
      ? -1
      : 1
    : x.kind === "folder"
      ? x.name.toLowerCase().localeCompare(y.name.toLowerCase()) || x.id.localeCompare(y.id)
      : y.at.localeCompare(x.at) || x.id.localeCompare(y.id);

function card(state: State, all: Item[], it: Item): ItemCard {
  const inside = all.filter((c) => c.parentId === it.id);
  const newest = inside.filter((c) => c.kind === "note").sort(order);
  const info = it.kind === "note" ? state.notes.get(it.id)! : null;
  return {
    id: it.id,
    kind: it.kind,
    name: it.name,
    parentId: it.parentId,
    role: "owner",
    owner: null,
    modified: info ? info.modified : (newest[0]?.at ?? null),
    savedAt: it.at,
    preview: info?.preview ?? null,
    previews: newest.slice(0, 4).map((c) => state.notes.get(c.id)!.preview),
    count: inside.length,
    shared: false,
  };
}

function cards(state: State, parentId: string | null): ItemCard[] {
  const all = items(state);
  return all
    .filter((it) => it.parentId === parentId)
    .sort(order)
    .map((it) => card(state, all, it));
}

/** The folders above something, from the top down. */
function pathOf(library: Library, parentId: string | null): Crumb[] {
  const path: Crumb[] = [];
  for (let up = parentId; up !== null && library.folders[up]; up = library.folders[up]!.parentId)
    path.unshift({ id: up, name: library.folders[up]!.name });
  return path;
}

// ------------------------------------------------------------------ reading

export const home = (state: State) => cards(state, null);

export function folder(state: State, id: string): Folder {
  const f = state.library.folders[id];
  if (!f) throw new NotFound({ id });
  const all = items(state);
  return {
    folder: card(state, all, all.find((it) => it.id === id)!),
    path: pathOf(state.library, f.parentId),
    items: cards(state, id),
  };
}

export function destinations({ library }: State): Destination[] {
  return Object.entries(library.folders)
    .map(([id, f]) => ({ id, name: f.name, parentId: f.parentId }))
    .sort((a, b) => a.name.toLowerCase().localeCompare(b.name.toLowerCase()) || a.id.localeCompare(b.id));
}

/** Where a note is (the folders above it). */
export function notePlace({ library }: State, id: string): Crumb[] {
  const n = library.notes[id];
  if (!n) throw new NotFound({ id });
  return pathOf(library, n.parentId);
}

// ------------------------------------------------------------------ changing

/** The folder something goes into: null (the top) or a folder. */
function into(library: Library, parentId: string | null) {
  if (parentId !== null && !library.folders[parentId]) {
    if (library.notes[parentId]) throw new NotAFolder({ id: parentId });
    throw new NotFound({ id: parentId });
  }
  return parentId;
}

export function createFolder(library: Library, id: string, name: string, parentId: string | null, now: string) {
  return {
    ...library,
    folders: { ...library.folders, [id]: { name, parentId: into(library, parentId), created: now } },
  };
}

/** A new note, in a folder (or at the top). */
export function addNote(library: Library, id: string, parentId: string | null): Library {
  return { ...library, notes: { ...library.notes, [id]: { parentId: into(library, parentId) } } };
}

/** Moving into another folder (a folder not into itself); renaming a folder. (A note's name is its
 *  document's title: the caller writes that.) */
export function patch(
  library: Library,
  id: string,
  change: { name?: string | undefined; parentId?: string | null | undefined },
) {
  const f = library.folders[id];
  const n = library.notes[id];
  if (!f && !n) throw new NotFound({ id });
  let next = library;
  if (change.parentId !== undefined) {
    const parent = into(library, change.parentId);
    if (f && pathOf(library, parent).some((c) => c.id === id)) throw new MoveIntoItself({ id });
    if (f && parent === id) throw new MoveIntoItself({ id });
    next = f
      ? { ...next, folders: { ...next.folders, [id]: { ...f, parentId: parent } } }
      : { ...next, notes: { ...next.notes, [id]: { parentId: parent } } };
  }
  if (f && change.name !== undefined)
    next = { ...next, folders: { ...next.folders, [id]: { ...next.folders[id]!, name: change.name } } };
  return next;
}

/** A folder goes with everything in it: the notes whose files go too. */
export function remove(library: Library, id: string) {
  if (!library.folders[id] && !library.notes[id]) throw new NotFound({ id });
  const folders = { ...library.folders };
  const notes = { ...library.notes };
  const gone = [id];
  for (let i = 0; i < gone.length; i++) {
    const at = gone[i]!;
    delete folders[at];
    for (const [c, f] of Object.entries(library.folders)) if (f.parentId === at) gone.push(c);
  }
  const goneNotes = Object.entries(library.notes)
    .filter(([n, { parentId }]) => n === id || (parentId !== null && gone.includes(parentId)))
    .map(([n]) => n);
  for (const n of goneNotes) delete notes[n];
  return { library: { version: 2 as const, folders, notes }, notes: goneNotes };
}
