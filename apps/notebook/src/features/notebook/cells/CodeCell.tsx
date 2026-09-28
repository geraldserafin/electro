import type { KeyboardEvent } from "react";
import { useTranslation } from "react-i18next";
import type { Cell } from "@/shared/model/types";
import { CodeEditor } from "./CodeEditor";
import { Outputs } from "./Outputs";
import { RunButton } from "./RunButton";

/** The editor's frame: outlined while its cell is worked on. */
export const editorFrame = "rounded-lg transition-shadow duration-150 group-data-focused/cell:shadow-island";

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
    <div className="flex gap-2 items-start">
      <RunButton run={run} running={running} label={t("code.run")} execution={cell.execution} />
      <div className="flex-1 min-w-0">
        <div className={editorFrame} onKeyDownCapture={runOnShiftEnter(run)}>
          <CodeEditor value={cell.source} onChange={(source) => update({ source })} />
        </div>
        <Outputs outputs={cell.outputs} />
      </div>
    </div>
  );
}
