/**
 * The vault: the user's notes as files in a git repository in this browser (repo.ts) — library.json
 * and notes/<id>.json (library.ts), firmware/<sha-256> for the programs they upload, components/<id>.json
 * for the components they made (features/components). What the
 * notebook changes is written at once; autosaving puts it into the session's one commit, and saving
 * ends the session: with GitHub connected, its commit joined with GitHub's and pushed.
 *
 * A note's revision counts its changes since the page was opened (a save must start from the
 * newest one): a save from an older one — the note was changed meanwhile, say by a sync that brought
 * GitHub's version — is a conflict, which the notebook lets the user settle.
 */
import { type NotebookDocument, NotFound, previewOf, RevisionConflict } from "@electro/notes-api";
import * as L from "./library";
import type { Author, Change, Remote, Repo } from "./repo";

const text = new TextDecoder();

export class Vault {
  private state: Promise<L.State> | null = null;
  private revisions = new Map<string, number>();
  private queue: Promise<unknown> = Promise.resolve();

  /** Told of every change, with the notes it changed (for autosaving, and the other tabs). */
  onChange: (notes: string[]) => void = () => {};

  constructor(readonly repo: Repo) {}

  /** One change at a time: each sees the one before. */
  private serially<A>(f: () => Promise<A>): Promise<A> {
    const next = this.queue.then(f, f);
    this.queue = next.catch(() => {});
    return next;
  }

  private async load(): Promise<L.State> {
    await this.repo.init();
    const ids = (await this.repo.list("notes")).filter((n) => n.endsWith(".json")).map((n) => n.slice(0, -5));
    const notes = new Map<string, L.NoteInfo>();
    await Promise.all(
      ids.map(async (id) => {
        const document = await this.document(id).catch((e) => {
          console.warn(`notes/${id}.json is not a note`, e); // (broken by hand on GitHub, say: left out)
          return null;
        });
        if (document) notes.set(id, info(document));
      }),
    );
    let stored = L.empty;
    try {
      const bytes = await this.repo.read("library.json");
      if (bytes) stored = JSON.parse(text.decode(bytes)) as L.Library;
    } catch (e) {
      // the folders are lost, not the notes: each at the top
      console.warn("library.json is not a library", e);
    }
    return { library: L.normalize(stored, notes.keys()), notes };
  }

  read(): Promise<L.State> {
    this.state ??= this.load();
    this.state.catch(() => {
      this.state = null;
    });
    return this.state;
  }

  private async document(id: string): Promise<NotebookDocument | null> {
    const bytes = await this.repo.read(L.notePath(id));
    return bytes && (JSON.parse(text.decode(bytes)) as NotebookDocument);
  }

  private async writeLibrary(state: L.State, library: L.Library) {
    await this.repo.write("library.json", `${JSON.stringify(library, null, 1)}\n`);
    this.state = Promise.resolve({ ...state, library });
  }

  // ------------------------------------------------------------------ notes

  revision = (id: string) => this.revisions.get(id) ?? 1;

  async note(id: string) {
    const state = await this.read();
    const path = L.notePlace(state, id);
    const document = await this.document(id);
    if (!document) throw new NotFound({ id });
    return { document, revision: this.revision(id), savedAt: document.modified, path, role: "owner" as const };
  }

  /** Create (``baseRevision`` null; into the folder ``parentId``) or change a note. */
  save(document: NotebookDocument, baseRevision: number | null, parentId: string | null | undefined) {
    return this.serially(async () => {
      const state = await this.read();
      const exists = state.notes.has(document.id);
      const current = exists ? this.revision(document.id) : 0;
      if (exists ? baseRevision !== current : baseRevision !== null)
        throw new RevisionConflict({ id: document.id, current, base: baseRevision });
      const library = exists ? state.library : L.addNote(state.library, document.id, parentId ?? null);
      await this.repo.write(L.notePath(document.id), `${JSON.stringify(document, null, 1)}\n`);
      const notes = new Map(state.notes).set(document.id, info(document));
      if (exists) this.state = Promise.resolve({ library, notes });
      else await this.writeLibrary({ library, notes }, library);
      this.revisions.set(document.id, current + 1);
      this.onChange([document.id]);
      return { revision: current + 1, savedAt: new Date().toISOString() };
    });
  }

  // ------------------------------------------------------------------ folders, moving, deleting

  createFolder(id: string, name: string, parentId: string | null) {
    return this.serially(async () => {
      const state = await this.read();
      const library = L.createFolder(state.library, id, name, parentId, new Date().toISOString());
      await this.writeLibrary(state, library);
      this.onChange([]);
      return L.folder({ ...state, library }, id).folder;
    });
  }

  /** Rename and/or move; a note's new name is its document's title (a new revision). */
  patch(id: string, change: { name?: string | undefined; parentId?: string | null | undefined }) {
    return this.serially(async () => {
      let state = await this.read();
      const library = L.patch(state.library, id, change);
      if (library !== state.library) await this.writeLibrary(state, library);
      state = { ...state, library };
      if (state.library.notes[id] && change.name !== undefined) {
        const document = await this.document(id);
        if (document && document.title !== change.name) {
          const renamed = { ...document, title: change.name };
          await this.repo.write(L.notePath(id), `${JSON.stringify(renamed, null, 1)}\n`);
          state = { ...state, notes: new Map(state.notes).set(id, info(renamed)) };
          this.state = Promise.resolve(state);
          this.revisions.set(id, this.revision(id) + 1);
        }
      }
      this.onChange(state.library.notes[id] ? [id] : []);
      const parentId = state.library.folders[id]?.parentId ?? state.library.notes[id]!.parentId;
      const siblings = parentId === null ? L.home(state) : L.folder(state, parentId).items;
      return siblings.find((c) => c.id === id)!;
    });
  }

  /** A folder goes with everything in it. */
  remove(id: string) {
    return this.serially(async () => {
      const state = await this.read();
      const { library, notes: gone } = L.remove(state.library, id);
      for (const note of gone) await this.repo.remove(L.notePath(note));
      const notes = new Map(state.notes);
      for (const note of gone) notes.delete(note);
      await this.writeLibrary({ library, notes }, library);
      this.onChange(gone);
    });
  }

  // ------------------------------------------------------------------ firmware

  async firmware(id: string) {
    return this.repo.read(`firmware/${id}`);
  }

  putFirmware(id: string, bytes: Uint8Array) {
    return this.serially(async () => {
      if ((await this.repo.read(`firmware/${id}`)) === null) {
        await this.repo.write(`firmware/${id}`, bytes);
        this.onChange([]);
      }
    });
  }

  // ------------------------------------------------------------------ one's own components

  /** The components the user made, as stored (a file that is not JSON: left out). */
  async components(): Promise<{ id: string; data: unknown }[]> {
    await this.read();
    const names = (await this.repo.list("components")).filter((n) => n.endsWith(".json"));
    const found = await Promise.all(
      names.map(async (name) => {
        try {
          const bytes = await this.repo.read(`components/${name}`);
          return bytes ? [{ id: name.slice(0, -5), data: JSON.parse(text.decode(bytes)) as unknown }] : [];
        } catch (e) {
          console.warn(`components/${name} is not a component`, e);
          return [];
        }
      }),
    );
    return found.flat();
  }

  putComponent(id: string, data: unknown) {
    return this.serially(async () => {
      await this.read();
      await this.repo.write(`components/${id}.json`, `${JSON.stringify(data, null, 1)}\n`);
      this.onChange([]);
    });
  }

  removeComponent(id: string) {
    return this.serially(async () => {
      await this.read();
      await this.repo.remove(`components/${id}.json`);
      this.onChange([]);
    });
  }

  // ------------------------------------------------------------------ saving

  /** Anything not saved yet (with GitHub: not on GitHub's main yet). */
  unsaved(connected: boolean) {
    return this.serially(async () => {
      await this.read();
      return this.repo.unsaved(connected);
    });
  }

  /** Changed elsewhere (another tab): read afresh; those notes have new revisions. */
  external(notes: readonly string[]) {
    this.state = null;
    for (const id of notes) this.revisions.set(id, this.revision(id) + 1);
  }

  /** git, one tab at a time (the file system is shared: LightningFS locks its own part). */
  private git<A>(f: () => Promise<A>): Promise<A> {
    const locks = typeof navigator === "undefined" ? undefined : navigator.locks;
    return this.serially(() => (locks ? locks.request("electro-vault-git", f) : f()));
  }

  /** Autosaving: the changes into the session's commit (one for the whole session, repo.ts), and
   *  with ``remote`` that commit on GitHub, on this browser's own branch. */
  autosave(author: Author, remote: Remote | null, device: string) {
    return this.git(async () => {
      await this.read();
      await this.repo.commitSession(this.message, author);
      if (remote) await this.repo.pushSession(remote, device);
    });
  }

  /**
   * The session saved and over: its commit made (or amended) the last time, and with ``remote``,
   * joined with GitHub's main and pushed there (its branch gone). The notes that changed here
   * (GitHub had newer versions of them: each has a new revision).
   */
  finish(author: Author, remote: Remote | null, device: string, copyTitle: (title: string) => string) {
    return this.git(async () => {
      await this.read();
      await this.repo.commitSession(this.message, author);
      await this.repo.endSession();
      if (!remote) return [];
      const changed = await this.repo.sync(remote, author, newId, copyTitle);
      await this.repo.dropSessionBranch(remote, device);
      const notes = changed.flatMap((p) => /^notes\/(.+)\.json$/.exec(p)?.[1] ?? []);
      this.external(notes);
      return notes;
    });
  }

  /** For the save button's card: what a save would put in (by what it is: a note's title, a
   *  component's name), when it last autosaved, and the history before it. */
  details() {
    return this.serially(async () => {
      const state = await this.read();
      const base = await this.repo.sessionBase();
      const [changes, history, autosaved] = await Promise.all([
        this.repo.workingChangesSince(base),
        this.repo.history(base),
        this.repo.autosavedAt(),
      ]);
      const items: Pending[] = [];
      for (const [path, change] of Object.entries(changes)) {
        const note = /^notes\/(.+)\.json$/.exec(path)?.[1];
        const component = /^components\/(.+)\.json$/.exec(path)?.[1];
        const title = async (at: string) => {
          const bytes = (await this.repo.read(at)) ?? (base ? await this.repo.readAt(base, at) : null);
          try {
            const data = bytes ? (JSON.parse(text.decode(bytes)) as { title?: string; name?: string }) : null;
            return data?.title ?? data?.name ?? "";
          } catch {
            return "";
          }
        };
        if (note) items.push({ what: "note", change, name: state.notes.get(note)?.title ?? (await title(path)) });
        else if (component) items.push({ what: "component", change, name: await title(path) });
        else if (path === "library.json") items.push({ what: "folders", change, name: "" });
        else if (path.startsWith("firmware/")) items.push({ what: "firmware", change, name: "" });
      }
      // library.json changes with every note added or deleted: said only when the folders alone changed
      const notes = items.some((i) => i.what === "note");
      return { changes: items.filter((i) => !(notes && i.what === "folders")), history, autosaved };
    });
  }

  /** What the session changed, said: `Edit "Pomiar"; add "Zadanie 4"`. */
  private message = async (changes: Record<string, Change>, base: string | null): Promise<string> => {
    const state = await this.read();
    const said: Record<Change, string[]> = { add: [], edit: [], delete: [] };
    let other = false;
    for (const [path, change] of Object.entries(changes)) {
      const id = /^notes\/(.+)\.json$/.exec(path)?.[1];
      if (!id) {
        other = true;
        continue;
      }
      let title = state.notes.get(id)?.title;
      if (title === undefined && base) {
        const before = await this.repo.readAt(base, path);
        title = before ? (JSON.parse(text.decode(before)) as { title?: string }).title : undefined;
      }
      said[change].push(`"${title || "Untitled"}"`);
    }
    const list = (titles: string[]) =>
      titles.length > 3 ? `${titles.slice(0, 3).join(", ")} and ${titles.length - 3} more` : titles.join(", ");
    const parts = (["edit", "add", "delete"] as const)
      .filter((c) => said[c].length)
      .map((c) => `${c} ${list(said[c])}`);
    const message = parts.length ? parts.join("; ") : other ? "organize the notes" : "update the notes";
    return message[0]!.toUpperCase() + message.slice(1);
  };
}

/** A change a save would put in: what it is to the user, how it changed, its name. */
export interface Pending {
  what: "note" | "component" | "folders" | "firmware";
  change: Change;
  name: string;
}

export const newId = () => crypto.randomUUID().replaceAll("-", "");

const info = (document: NotebookDocument): L.NoteInfo => ({
  title: document.title,
  modified: document.modified,
  preview: previewOf(document),
});
