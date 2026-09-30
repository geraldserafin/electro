// A code cell: a block like a small editor — the code edge to edge, run and [n] floating in its top
// right corner (no bar: one file, nothing to choose), and under it what the code printed, on the
// page's own colour.
import type { KeyboardEvent } from "react";
import { useTranslation } from "react-i18next";
import type { Cell } from "@/shared/model/types";
import { block, RunButton } from "./CellBar";
import { CodeEditor } from "./CodeEditor";
import { Outputs } from "./Outputs";

/** Shift+Enter in the editor runs, instead of a new line. */
export const runOnShiftEnter = (run: () => void) => (e: KeyboardEvent) => {
  if (e.key === "Enter" && e.shiftKey) {
    e.preventDefault();
    e.stopPropagation();
    run();
  }
};

export function CodeCell({
  cell,
  update,
  run,
  running,
}: {
  cell: Extract<Cell, { type: "code" }>;
  update: (patch: Partial<Cell>) => void;
  run: () => void;
  running: boolean;
}) {
  const { t } = useTranslation("notebook");
  return (
    <div className={block}>
      <div className="relative" onKeyDownCapture={runOnShiftEnter(run)}>
        <CodeEditor value={cell.source} onChange={(source) => update({ source })} fill />
        <div className="absolute top-1.5 right-1.5 z-2">
          <RunButton run={run} running={running} label={t("code.run")} execution={cell.execution} />
        </div>
      </div>
      {cell.outputs.length > 0 && (
        <div className="border-t border-line bg-bg px-3 py-2.5">
          <Outputs outputs={cell.outputs} />
        </div>
      )}
    </div>
  );
}
