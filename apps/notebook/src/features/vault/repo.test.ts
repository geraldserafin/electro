import * as fs from "node:fs";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import type { NotebookDocument } from "@electro/notes-api";
import git from "isomorphic-git";
import { afterEach, describe, expect, it } from "vitest";
import { type Fs, Repo } from "./repo";
import { Vault } from "./vault";

const author = { name: "Test", email: "test@example.com" };
const dirs: string[] = [];
afterEach(() => {
  for (const d of dirs.splice(0)) rmSync(d, { recursive: true, force: true });
});

async function fresh() {
  const dir = mkdtempSync(join(tmpdir(), "vault-"));
  dirs.push(dir);
  const repo = new Repo(fs as unknown as Fs, dir);
  return { vault: new Vault(repo), repo, dir };
}

const doc = (id: string, title: string, text = "") =>
  ({
    format: "electro-notebook",
    id,
    title,
    version: 2,
    created: "2026-09-30T10:00:00Z",
    modified: "2026-09-30T10:00:00Z",
    settings: { codeInPdf: false },
    cells: [{ id: "c1", type: "markdown", source: text || "Zażółć gęślą jaźń" }],
  }) as unknown as NotebookDocument;

/** A commit made elsewhere (GitHub's): ``files`` on top of ``parent``'s. */
async function theirCommit(repo: Repo, parent: string, files: Record<string, string>) {
  const tree = { ...(await repo.tree(parent)) };
  for (const [path, content] of Object.entries(files))
    tree[path] = await git.writeBlob({ fs: repo.fs, dir: repo.dir, blob: new TextEncoder().encode(content) });
  // (a tree of trees: the paths' folders)
  const build = async (prefix: string): Promise<string> => {
    const here = new Map<string, { mode: string; path: string; oid: string; type: "blob" | "tree" }>();
    for (const [path, oid] of Object.entries(tree)) {
      if (!path.startsWith(prefix)) continue;
      const [name, ...rest] = path.slice(prefix.length).split("/");
      if (rest.length)
        here.set(name!, { mode: "040000", path: name!, oid: await build(`${prefix}${name}/`), type: "tree" });
      else here.set(name!, { mode: "100644", path: name!, oid, type: "blob" });
    }
    return git.writeTree({ fs: repo.fs, dir: repo.dir, tree: [...here.values()] });
  };
  return git.commit({
    fs: repo.fs,
    dir: repo.dir,
    message: "theirs",
    author,
    tree: await build(""),
    parent: [parent],
    ref: "refs/remotes/origin/main",
    noUpdateBranch: true,
  });
}

describe("the vault in a git repository", () => {
  it("keeps notes as they are edited, and commits them on saving", async () => {
    const { vault, repo } = await fresh();
    await vault.createFolder("f1", "Lab", null);
    const saved = await vault.save(doc("n1", "Pomiar"), null, "f1");
    expect(saved.revision).toBe(1);
    expect(await vault.unsaved(false)).toBe(true);
    expect((await vault.note("n1")).path).toEqual([{ id: "f1", name: "Lab" }]);

    await vault.finish(author, null, "d", (t) => t);
    expect(await vault.unsaved(false)).toBe(false);
    expect(
      Object.keys(await repo.tree(await git.resolveRef({ fs: repo.fs, dir: repo.dir, ref: "HEAD" }))).sort(),
    ).toEqual(["library.json", "notes/n1.json"]);

    await vault.patch("n1", { name: "Nowy" });
    expect((await vault.note("n1")).document.title).toBe("Nowy");
    await expect(vault.save(doc("n1", "stale"), 1, undefined)).rejects.toMatchObject({ _tag: "RevisionConflict" });
    await vault.remove("f1");
    await vault.finish(author, null, "d", (t) => t);
    expect(await vault.unsaved(false)).toBe(false);
    await expect(vault.note("n1")).rejects.toMatchObject({ _tag: "NotFound" });
  });

  it("makes one commit a session, however often it autosaves, saying what the session changed", async () => {
    const { vault, repo } = await fresh();
    const log = async () => (await git.log({ fs: repo.fs, dir: repo.dir })).map((c) => c.commit.message.trim());
    await vault.save(doc("n1", "Pomiar"), null, null);
    await vault.finish(author, null, "d", (t) => t);
    expect(await log()).toEqual(['Add "Pomiar"']);

    // a session: edits, autosaved three times
    await vault.save(doc("n1", "Pomiar", "v2"), 1, undefined);
    await vault.autosave(author, null, "d");
    await vault.save(doc("n2", "Zadanie 4"), null, null);
    await vault.autosave(author, null, "d");
    await vault.autosave(author, null, "d"); // nothing new: nothing happens
    await vault.save(doc("n1", "Pomiar", "v3"), 2, undefined);
    await vault.finish(author, null, "d", (t) => t);
    expect(await log()).toEqual(['Edit "Pomiar"; add "Zadanie 4"', 'Add "Pomiar"']);
    expect((await vault.note("n1")).document.cells[0]).toMatchObject({ source: "v3" });

    // saving with nothing changed: no commit
    await vault.finish(author, null, "d", (t) => t);
    expect(await log()).toHaveLength(2);

    // a session whose change went back: no commit at all (and an edit of the same size, in the same
    // second, is seen: "v3" → "v4" → "v3")
    await vault.save(doc("n1", "Pomiar", "v4"), 3, undefined);
    await vault.autosave(author, null, "d");
    expect(await log()).toHaveLength(3);
    await vault.save(doc("n1", "Pomiar", "v3"), 4, undefined);
    await vault.autosave(author, null, "d");
    await vault.finish(author, null, "d", (t) => t);
    expect(await log()).toHaveLength(2);
    expect(await vault.unsaved(false)).toBe(false);

    // a deleted note is named in the message, too
    await vault.remove("n2");
    await vault.finish(author, null, "d", (t) => t);
    expect((await log())[0]).toBe('Delete "Zadanie 4"');
  });

  it("tells the save button what a save would put in, and the history before it", async () => {
    const { vault } = await fresh();
    expect(await vault.details()).toMatchObject({ changes: [], history: [], autosaved: null });
    await vault.save(doc("n1", "Pomiar"), null, null);
    await vault.save(doc("n2", "Zadanie 4"), null, null);
    await vault.finish(author, null, "d", (t) => t);
    // a session: one note edited (autosaved), one deleted (not yet), one added
    await vault.save(doc("n1", "Pomiar", "v2"), 1, undefined);
    await vault.autosave(author, null, "d");
    await vault.remove("n2");
    await vault.save(doc("n3", "Nowa"), null, null);
    const d = await vault.details();
    const notes = d.changes.filter((c) => c.what === "note").map((c) => [c.change, c.name]);
    expect(notes.sort()).toEqual([
      ["add", "Nowa"],
      ["delete", "Zadanie 4"],
      ["edit", "Pomiar"],
    ]);
    expect(d.changes.some((c) => c.what === "folders")).toBe(false); // (the notes say it: library.json is noise)
    expect(d.autosaved).toBeGreaterThan(0);
    expect(d.history.map((c) => [c.message, c.onGitHub])).toEqual([['Add "Pomiar", "Zadanie 4"', false]]);
  });

  it("reads a vault with a broken library: the notes are all there, at the top", async () => {
    const { vault, repo } = await fresh();
    await vault.createFolder("f1", "Lab", null);
    await vault.save(doc("n1", "Pomiar"), null, "f1");
    await repo.write("library.json", "{ not json");
    await repo.write("notes/bad.json", "nope");
    const again = new Vault(repo);
    const state = await again.read();
    expect([...state.notes.keys()]).toEqual(["n1"]);
    expect(state.library.notes).toEqual({ n1: { parentId: null } });
  });

  it("takes GitHub's line as it is when there is nothing here it lacks", async () => {
    const { vault, repo } = await fresh();
    await vault.save(doc("n1", "One"), null, null);
    await vault.finish(author, null, "d", (t) => t);
    const head = await git.resolveRef({ fs: repo.fs, dir: repo.dir, ref: "HEAD" });
    const theirs = await theirCommit(repo, head, { "notes/n1.json": JSON.stringify(doc("n1", "One, edited")) });
    expect(
      await repo.integrate(
        theirs,
        author,
        () => "x",
        (t) => t,
      ),
    ).toEqual(["notes/n1.json"]);
    const again = new Vault(repo);
    expect((await again.note("n1")).document.title).toBe("One, edited");
  });

  it("joins two vaults that began apart: all the notes of both", async () => {
    // GitHub's: a vault from another browser
    const other = await fresh();
    await other.vault.createFolder("fg", "Z GitHuba", null);
    await other.vault.save(doc("g1", "Stara notatka"), null, "fg");
    await other.vault.finish(author, null, "d", (t) => t);
    // ours: notes made here before connecting
    const { vault, repo } = await fresh();
    await vault.createFolder("fl", "Lokalny", null);
    await vault.save(doc("l1", "Nowa notatka"), null, "fl");
    await vault.finish(author, null, "d", (t) => t);
    // their commits fetched here
    const theirHead = await git.resolveRef({ fs: other.repo.fs, dir: other.repo.dir, ref: "HEAD" });
    for (const oid of (await git.log({ fs: other.repo.fs, dir: other.repo.dir })).map((c) => c.oid)) {
      const { object, type } = await git.readObject({
        fs: other.repo.fs,
        dir: other.repo.dir,
        oid,
        format: "deflated",
      });
      await git.writeObject({ fs: repo.fs, dir: repo.dir, object, type, format: "deflated", oid } as never);
      const tree = await other.repo.tree(oid);
      for (const blob of Object.values(tree)) {
        const b = await git.readObject({ fs: other.repo.fs, dir: other.repo.dir, oid: blob, format: "deflated" });
        await git.writeObject({
          fs: repo.fs,
          dir: repo.dir,
          object: b.object,
          type: b.type as never,
          format: "deflated",
          oid: blob,
        });
      }
      const walk = async (treeOid: string) => {
        const t = await git.readObject({ fs: other.repo.fs, dir: other.repo.dir, oid: treeOid, format: "deflated" });
        await git.writeObject({
          fs: repo.fs,
          dir: repo.dir,
          object: t.object,
          type: t.type as never,
          format: "deflated",
          oid: treeOid,
        });
        for (const e of (await git.readTree({ fs: other.repo.fs, dir: other.repo.dir, oid: treeOid })).tree)
          if (e.type === "tree") await walk(e.oid);
      };
      await walk((await git.readCommit({ fs: other.repo.fs, dir: other.repo.dir, oid })).commit.tree);
    }

    await repo.integrate(
      theirHead,
      author,
      () => "x",
      (t) => t,
    );
    const again = new Vault(repo);
    const state = await again.read();
    expect([...state.notes.values()].map((n) => n.title).sort()).toEqual(["Nowa notatka", "Stara notatka"]);
    expect(
      Object.values(state.library.folders)
        .map((f) => f.name)
        .sort(),
    ).toEqual(["Lokalny", "Z GitHuba"]);
    expect((await again.note("g1")).path).toEqual([{ id: "fg", name: "Z GitHuba" }]);
    expect(await repo.unsaved(false)).toBe(false);
  });

  it("joins two lines: both notes' changes, and a copy where both changed one note", async () => {
    const { vault, repo } = await fresh();
    await vault.save(doc("n1", "Shared"), null, null);
    await vault.save(doc("n2", "Mine"), null, null);
    await vault.finish(author, null, "d", (t) => t);
    const base = await git.resolveRef({ fs: repo.fs, dir: repo.dir, ref: "HEAD" });

    // here: n1 and n2 edited, a new note
    await vault.save(doc("n1", "Shared", "ours"), 1, undefined);
    await vault.save(doc("n2", "Mine, edited"), 1, undefined);
    await vault.save(doc("n3", "New here"), null, null);
    await vault.finish(author, null, "d", (t) => t);
    // there: n1 edited too, and a note of their own
    const theirLibrary = JSON.parse(new TextDecoder().decode((await repo.read("library.json"))!));
    delete theirLibrary.notes.n3;
    theirLibrary.notes.n4 = { parentId: null };
    const theirs = await theirCommit(repo, base, {
      "notes/n1.json": JSON.stringify(doc("n1", "Shared", "theirs")),
      "notes/n4.json": JSON.stringify(doc("n4", "From GitHub")),
      "library.json": JSON.stringify(theirLibrary),
    });

    const changed = await repo.integrate(
      theirs,
      author,
      () => "copy",
      (t) => `${t} (GitHub)`,
    );
    expect(changed.sort()).toEqual(["library.json", "notes/copy.json", "notes/n4.json"]);
    const again = new Vault(repo);
    const titles = (await again.read()).notes;
    expect([...titles.values()].map((n) => n.title).sort()).toEqual([
      "From GitHub",
      "Mine, edited",
      "New here",
      "Shared",
      "Shared (GitHub)",
    ]);
    expect((await again.note("n1")).document.cells[0]).toMatchObject({ source: "ours" });
    expect((await again.note("copy")).document.cells[0]).toMatchObject({ source: "theirs" });
    // a merge commit of both lines, and nothing left uncommitted
    const [merge] = await git.log({ fs: repo.fs, dir: repo.dir, depth: 1 });
    expect(merge!.commit.parent).toHaveLength(2);
    expect(await repo.unsaved(false)).toBe(false);
  });
});
