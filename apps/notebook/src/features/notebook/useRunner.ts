// Running cells in Python: code cells print their outputs, schematics are solved. One cell at a
// time per cell (``running``); "run all" goes through them in order.
import { useRef, useState, type RefObject } from "react";
import { kernel } from "@/features/python";
import type { Cell, Notebook, SchematicData } from "@/shared/model/types";

export function useRunner(latest: RefObject<Notebook>, update: (id: string, patch: Partial<Cell>) => void) {
  const [running, setRunning] = useState<Set<string>>(new Set());
  const executions = useRef(0);

  const schematics = (): Record<string, SchematicData> =>
    Object.fromEntries(latest.current.cells.flatMap((c) => (c.type === "schematic" ? [[c.name, c.schematic] as const] : [])));

  const busy = async (id: string, work: () => Promise<void>) => {
    setRunning((r) => new Set(r).add(id));
    try {
      await kernel.ready;
      await work();
    } finally {
      setRunning((r) => {
        const next = new Set(r);
        next.delete(id);
        return next;
      });
    }
  };

  const run = (id: string) => {
    const cell = latest.current.cells.find((c) => c.id === id);
    if (!cell || cell.type !== "code") return Promise.resolve();
    return busy(id, async () => {
      try {
        const outputs = await kernel.run(cell.source, schematics(), String(latest.current.settings.symbols ?? "iec"));
        update(id, { outputs, execution: ++executions.current });
      } catch (error) {
        update(id, { outputs: [{ type: "error", data: String(error) }] });
      }
    });
  };

  /** ``schematic``: the drawing to solve, when it was just changed (the cell's state lags behind). */
  const simulate = (id: string, schematic?: SchematicData) => {
    const cell = latest.current.cells.find((c) => c.id === id);
    if (!cell || cell.type !== "schematic") return Promise.resolve();
    return busy(id, async () => {
      try {
        const { results, problems } = await kernel.simulate(schematic ?? cell.schematic);
        update(id, { results, problems, stale: false });
      } catch (error) {
        update(id, { results: {}, problems: [{ kind: "error", text: String(error) }], stale: false });
      }
    });
  };

  const runAll = async () => {
    for (const cell of latest.current.cells) {
      if (cell.type === "code") await run(cell.id);
      if (cell.type === "schematic" && cell.results) await simulate(cell.id);
    }
  };

  return { running, run, simulate, runAll };
}
