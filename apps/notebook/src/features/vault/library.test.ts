import { type NotebookDocument, previewOf } from "@electro/notes-api";
import { describe, expect, it } from "vitest";
import * as L from "./library";

const doc = (id: string, title: string, modified: string) =>
  ({
    format: "electro-notebook",
    id,
    title,
    version: 2,
    created: modified,
    modified,
    settings: { codeInPdf: false },
    cells: [{ id: "c1", type: "markdown", source: `# ${title}` }],
  }) as unknown as NotebookDocument;

const t = (n: number) => `2026-09-30T10:00:0${n}.000Z`;

function sample(): L.State {
  let library = L.createFolder(L.empty, "f1", "Zeta", null, t(0));
  library = L.createFolder(library, "f2", "alfa", null, t(1));
  library = L.createFolder(library, "f3", "Inner", "f1", t(2));
  library = L.addNote(library, "n1", null);
  library = L.addNote(library, "n2", null);
  library = L.addNote(library, "n3", "f3");
  const notes = new Map(
    [doc("n1", "Old", t(3)), doc("n2", "New", t(4)), doc("n3", "Deep", t(5))].map((d) => [
      d.id,
      { title: d.title, modified: d.modified, preview: previewOf(d) },
    ]),
  );
  return { library, notes };
}

describe("the vault's library", () => {
  it("lists folders first by name, then notes the newest first", () => {
    expect(L.home(sample()).map((c) => c.id)).toEqual(["f2", "f1", "n2", "n1"]);
  });

  it("gives a folder its path, its contents and its notes' pictures", () => {
    const state = sample();
    const inner = L.folder(state, "f3");
    expect(inner.path).toEqual([{ id: "f1", name: "Zeta" }]);
    expect(inner.items.map((c) => c.name)).toEqual(["Deep"]);
    expect(inner.folder.previews).toHaveLength(1);
    expect(L.folder(state, "f1").folder.count).toBe(1);
    expect(() => L.folder(state, "n1")).toThrow(expect.objectContaining({ _tag: "NotFound" }));
    expect(L.notePlace(state, "n3").map((c) => c.id)).toEqual(["f1", "f3"]);
  });

  it("puts things only into folders", () => {
    expect(() => L.addNote(sample().library, "n9", "n1")).toThrow(expect.objectContaining({ _tag: "NotAFolder" }));
  });

  it("moves, and a folder not into itself", () => {
    const { library } = sample();
    expect(() => L.patch(library, "f1", { parentId: "f3" })).toThrow(
      expect.objectContaining({ _tag: "MoveIntoItself" }),
    );
    expect(L.patch(library, "n1", { parentId: "f2" }).notes.n1).toEqual({ parentId: "f2" });
    expect(L.patch(library, "f2", { name: "Beta" }).folders.f2?.name).toBe("Beta");
  });

  it("removes a folder with everything in it", () => {
    const { library, notes } = L.remove(sample().library, "f1");
    expect(notes).toEqual(["n3"]);
    expect(Object.keys(library.folders)).toEqual(["f2"]);
    expect(Object.keys(library.notes).sort()).toEqual(["n1", "n2"]);
  });

  it("keeps every note there is, and nothing in a folder that is gone", () => {
    const { library } = sample();
    const { f3: _, ...folders } = library.folders;
    const fixed = L.normalize({ ...library, folders }, ["n1", "n3", "n4"]);
    expect(fixed.notes).toEqual({ n1: { parentId: null }, n3: { parentId: null }, n4: { parentId: null } });
  });

  it("joins two libraries: each change from the side that made it", () => {
    const base = sample().library;
    const ours = L.patch(L.addNote(base, "mine", null), "n1", { parentId: "f2" });
    const theirs = L.remove(L.createFolder(base, "f9", "Theirs", null, t(9)), "n2").library;
    const joined = L.mergeLibraries(base, ours, theirs);
    expect(Object.keys(joined.folders).sort()).toEqual(["f1", "f2", "f3", "f9"]);
    expect(Object.keys(joined.notes).sort()).toEqual(["mine", "n1", "n3"]);
    expect(joined.notes.n1).toEqual({ parentId: "f2" });
  });
});
