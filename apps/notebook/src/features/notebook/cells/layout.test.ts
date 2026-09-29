import { describe, expect, it } from "vitest";
import { clean, close, dock, flat, initial, moveFlat, moveTo, open, split } from "./layout";

const files = ["board", "circuit", "ARD_1"];
const tabs = (l: ReturnType<typeof initial>) => l.groups.map((g) => `${g.tabs.join(",")}:${g.active}`);

describe("the cell's editor layout", () => {
  it("opens with every file in one group, the drawing (or the code) shown", () => {
    expect(tabs(initial(files, false))).toEqual(["board,circuit,ARD_1:board"]);
    expect(tabs(initial(files, true))).toEqual(["board,circuit,ARD_1:circuit"]);
  });

  it("a tab click shows the file in its group (it takes the group over)", () => {
    expect(tabs(open(initial(files, false), "circuit", files))).toEqual(["board,circuit,ARD_1:circuit"]);
  });

  it("a tab dragged to a group's side splits it off into a new group there", () => {
    const right = split(initial(files, false), "circuit", 0, "right", files);
    expect(tabs(right)).toEqual(["board,ARD_1:board", "circuit:circuit"]);
    expect(right.focus).toBe(1);
    const left = split(initial(files, false), "ARD_1", 0, "left", files);
    expect(tabs(left)).toEqual(["ARD_1:ARD_1", "board,circuit:board"]);
  });

  it("a tab dragged into another group moves there; an emptied group goes", () => {
    const two = split(initial(files, false), "circuit", 0, "right", files);
    expect(tabs(moveTo(two, "circuit", 0, files))).toEqual(["board,ARD_1,circuit:circuit"]);
  });

  it("a group left alone fills the width again (after a split is closed or moved back)", () => {
    const two = split(initial(files, false), "circuit", 0, "right", files);
    expect(two.groups.map((g) => g.size)).toEqual([1, 1]);
    expect(moveTo(two, "circuit", 0, files).groups.map((g) => g.size)).toEqual([1]);
    expect(close(two, "circuit", files).groups.map((g) => g.size)).toEqual([1]);
    const back = split(two, "circuit", 0, "left", files); // right, then dragged to the left
    expect(back.groups.map((g) => g.size)).toEqual([1, 1]);
    expect(close(back, "circuit", files).groups.map((g) => g.size)).toEqual([1]);
  });

  it("a tab dragged along its own bar, or into the other bar, goes where it is let go", () => {
    const one = initial(files, false);
    expect(tabs(moveTo(one, "ARD_1", 0, files, 0))).toEqual(["ARD_1,board,circuit:ARD_1"]);
    expect(tabs(moveTo(one, "board", 0, files, 1))).toEqual(["circuit,board,ARD_1:board"]);
    const two = split(one, "circuit", 0, "right", files);
    expect(tabs(moveTo(two, "ARD_1", 1, files, 0))).toEqual(["board:board", "ARD_1,circuit:ARD_1"]);
    expect(tabs(moveTo(two, "circuit", 0, files, 1))).toEqual(["board,circuit,ARD_1:circuit"]); // the bars join
  });

  it("two groups at most: an outer edge swaps them, or takes the tab over", () => {
    const two = split(initial(files, false), "circuit", 0, "right", files);
    expect(tabs(dock(two, "circuit", "left", files))).toEqual(["circuit:circuit", "board,ARD_1:board"]); // they trade places
    expect(tabs(split(two, "circuit", 0, "left", files))).toEqual(["circuit:circuit", "board,ARD_1:board"]);
    expect(tabs(dock(two, "ARD_1", "right", files))).toEqual(["board:board", "circuit,ARD_1:ARD_1"]); // it joins that side
    expect(split(two, "ARD_1", 1, "right", files).groups.length).toBe(2);
  });

  it("the notebook shows one bar (the split kept for full screen); a tab moved there keeps it", () => {
    const two = split(initial(files, false), "circuit", 0, "right", files);
    expect(tabs(flat(two))).toEqual(["board,ARD_1,circuit:circuit"]);
    expect(tabs(moveFlat(two, "circuit", 0, files))).toEqual(["circuit,board,ARD_1:circuit"]);
    expect(tabs(flat(moveFlat(two, "board", 1, files)))).toEqual(["ARD_1,board,circuit:board"]); // before the tab it lands on
  });

  it("a tab closed in a split goes back to the first group; every file always has a tab", () => {
    const two = split(initial(files, false), "circuit", 0, "right", files);
    expect(tabs(close(two, "circuit", files))).toEqual(["board,ARD_1,circuit:board"]);
    expect(tabs(clean({ groups: [{ tabs: ["circuit"], active: "circuit", size: 1 }], focus: 0 }, files)))
      .toEqual(["circuit,board,ARD_1:circuit"]); // a new Arduino's sketch, and so on
    expect(tabs(clean(initial(files, false), ["board", "circuit"]))).toEqual(["board,circuit:board"]); // one gone
  });
});
