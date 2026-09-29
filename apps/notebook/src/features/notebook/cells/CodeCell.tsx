// A code cell: a block like a small editor — its bar (the tab, run and [n], the cell's tools),
// the code edge to edge, and under it what the code printed, on the page's own colour.
import type { KeyboardEvent } from "react";
import { useTranslation } from "react-i18next";
import type { Cell } from "@/shared/model/types";
import { CodeIcon } from "@/shared/ui/icons";
import { block, CellBar, RunButton, tabLook } from "./CellBar";
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

export function CodeCell({ cell, update, run, running }: {
  cell: Extract<Cell, { type: "code" }>; update: (patch: Partial<Cell>) => void; run: () => void; running: boolean;
}) {
  const { t } = useTranslation("notebook");
  return (
    <div className={block}>
      <CellBar label={t("cell.tabs")}
               tabs={<span role="tab" aria-selected className={tabLook(true)}><CodeIcon /> Python</span>}
               run={<RunButton run={run} running={running} label={t("code.run")} execution={cell.execution} />} />
      <div onKeyDownCapture={runOnShiftEnter(run)}>
        <CodeEditor value={cell.source} onChange={(source) => update({ source })} fill />
      </div>
      {cell.outputs.length > 0 && (
        <div className="border-t border-line bg-bg px-3 py-2.5">
          <Outputs outputs={cell.outputs} />
        </div>
      )}
    </div>
  );
}
