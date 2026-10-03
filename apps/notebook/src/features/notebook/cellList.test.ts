import { describe, expect, it } from "vitest";
import type { Cell } from "@/shared/model/types";
import { moveSection } from "./cellList";

const md = (id: string, source: string): Cell => ({ id, type: "markdown", source });
const texts = (cells: Cell[]) => cells.map((c) => (c.type === "markdown" ? c.source : c.id));

describe("moveSection", () => {
  const cells = [md("a", "# A\nintro\n## B\nbee\n## C\nsee"), md("d", "# D\ndee")];

  it("moves a section from within a text, cutting it", () => {
    // ## C (line 4 of a) up to the end of a, before ## B
    const out = moveSection(cells, { cell: "a", line: 4 }, { cell: "d", line: 0 }, { cell: "a", line: 2 });
    expect(texts(out)).toEqual(["# A\nintro", "## C\nsee", "## B\nbee", "# D\ndee"]);
  });

  it("moves a whole cell's section to the end", () => {
    const out = moveSection(cells, { cell: "a", line: 0 }, { cell: "d", line: 0 }, null);
    expect(texts(out)).toEqual(["# D\ndee", "# A\nintro\n## B\nbee\n## C\nsee"]);
  });

  it("leaves the note as it is when dropped inside itself", () => {
    expect(moveSection(cells, { cell: "a", line: 2 }, { cell: "a", line: 4 }, { cell: "a", line: 2 })).toBe(cells);
    expect(moveSection(cells, { cell: "a", line: 2 }, { cell: "a", line: 4 }, { cell: "a", line: 4 })).toBe(cells);
  });
});
