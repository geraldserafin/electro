// The test drawings as the run button sends them to be solved: kept as fixtures/problems.json, which
// the kernel's tests solve (apps/notebook/python/test_kernel.py) — so a drawing's way to its numbers is
// checked end to end, half here and half there.
import { expect, it } from "vitest";
import type { SchematicData } from "@/shared/model/types";
import golden from "./fixtures/netlists.json";
import { library } from "./library";
import { solveData } from "./problem";

const cases = golden as unknown as Record<string, { schematic: SchematicData }>;

it("the test drawings, as problems", async () => {
  const sought: Record<string, string[]> = {
    voltage_between: ["U:R1", "I:Rw", "R:U1:U1"],
    terminal_on_corner: ["U:R1", "value:E1"],
  };
  const problems = Object.fromEntries(
    Object.entries(cases).map(([name, c]) => [
      name,
      solveData({ ...c.schematic, find: sought[name] ?? c.schematic.find }, library),
    ]),
  );
  await expect(`${JSON.stringify(problems, null, 1)}\n`).toMatchFileSnapshot("./fixtures/problems.json");
});
