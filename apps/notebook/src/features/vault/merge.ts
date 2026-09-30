/**
 * Joining two lines of work on the vault (this browser's and GitHub's, when both went on from where
 * they last met), file by file: what only one side changed comes from that side. Where both changed
 * the same file:
 *   library.json   folder by folder, note by note, the same way (library.ts)
 *   a note         this browser's stays; GitHub's comes too, as a copy beside it (nothing is lost)
 *   anything else  this browser's (firmware files are named by their content: never different)
 * A note changed on one side and deleted on the other stays.
 */
import { type Library, mergeLibraries, notePath } from "./library";

/** A tree: path → the blob's id. */
export type Tree = Readonly<Record<string, string>>;

/** What to change in ``ours`` (a file's new bytes, or null: gone). */
export type Changes = Record<string, Uint8Array | null>;

const text = new TextDecoder();
const bytes = (s: string) => new TextEncoder().encode(s);
const json = <A>(b: Uint8Array | null, fallback: A): A => (b === null ? fallback : (JSON.parse(text.decode(b)) as A));

export async function merge(
  { base, ours, theirs }: { base: Tree; ours: Tree; theirs: Tree },
  read: (oid: string) => Promise<Uint8Array>,
  newId: () => string,
  copyTitle: (title: string) => string,
): Promise<Changes> {
  const changes: Changes = {};
  const both: string[] = [];
  for (const path of new Set([...Object.keys(ours), ...Object.keys(theirs)])) {
    const [b, o, t] = [base[path], ours[path], theirs[path]];
    if (o === t || t === b) continue; // the same, or only ours changed
    if (o === b)
      changes[path] = t === undefined ? null : await read(t); // only theirs changed
    else both.push(path);
  }
  const blob = (oid: string | undefined) => (oid === undefined ? Promise.resolve(null) : read(oid));
  const theirCopies: [string, string][] = []; // [a copy's id, the note it copies]
  for (const path of both) {
    const [o, t] = [ours[path], theirs[path]];
    const note = /^notes\/(.+)\.json$/.exec(path)?.[1];
    if (path === "library.json" || !note) continue;
    if (o === undefined)
      changes[path] = await read(t!); // we deleted it, they changed it: it stays
    else if (t !== undefined) {
      const id = newId();
      const document = json<Record<string, unknown>>(await read(t), {});
      changes[notePath(id)] = bytes(
        JSON.stringify({ ...document, id, title: copyTitle(String(document.title ?? "")) }, null, 1),
      );
      theirCopies.push([id, note]);
    }
  }
  const empty: Library = { version: 2, folders: {}, notes: {} };
  const [lb, lo, lt] = await Promise.all(
    [base, ours, theirs].map(async (tree) => json(await blob(tree["library.json"]), empty)),
  );
  // (a 3-way merge of the library is right whoever changed it: with the copies, it is written anew)
  let library = both.includes("library.json") || theirCopies.length ? mergeLibraries(lb!, lo!, lt!) : null;
  if (library && theirCopies.length) {
    const notes = { ...library.notes };
    for (const [id, of] of theirCopies) notes[id] = { parentId: lt!.notes[of]?.parentId ?? null };
    library = { ...library, notes };
  }
  if (library) changes["library.json"] = bytes(JSON.stringify(library, null, 1));
  return changes;
}
