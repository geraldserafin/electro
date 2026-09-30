import { describe, expect, it } from "vitest";
import { newCell } from "@/shared/model/cells";
import { blank } from "@/shared/model/format";
import type { Cell } from "@/shared/model/types";
import { decodeNote, encodeNote } from "./link";

describe("a note in a link", () => {
  it("comes back as it was, without what runs left in it", async () => {
    const code = { ...newCell("code"), source: "print(1)", outputs: [{ type: "text" as const, data: "1" }] };
    const md = { ...newCell("markdown"), source: "# Zadanie ąę ∠" };
    const note = { ...blank("Test"), cells: [md, code] as Cell[] };
    const fragment = await encodeNote(note);
    expect(fragment).toMatch(/^[\w-]+$/); // safe in an address, as it is
    const back = await decodeNote(`#${fragment}`);
    expect(back.title).toBe("Test");
    expect(
      back.cells.map((c) =>
        c.type === "code" ? [c.source, c.outputs.length] : c.type === "markdown" ? c.source : null,
      ),
    ).toEqual(["# Zadanie ąę ∠", ["print(1)", 0]]);
  });

  it("refuses a fragment that is not one", async () => {
    await expect(decodeNote("#not-a-note")).rejects.toThrow();
  });
});
