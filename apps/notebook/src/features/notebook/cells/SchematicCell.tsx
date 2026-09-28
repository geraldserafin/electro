import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { usePdf } from "@/features/pdf-export";
import { kernel } from "@/features/python";
import { PdfDrawing, SchematicEditor, type Camera } from "@/features/schematic";
import type { Cell, SchematicData, SchematicView, SymbolLibrary } from "@/shared/model/types";
import { Flash } from "@/shared/ui/icons";
import { CodeEditor } from "./CodeEditor";
import { editorFrame, runOnShiftEnter } from "./CodeCell";
import { NameBox } from "./NameBox";
import { errorBox } from "./Outputs";
import { Problems } from "./Problems";
import { ResultsTable } from "./ResultsTable";
import { RunButton } from "./RunButton";
import { ViewSwitch } from "./ViewSwitch";
import { cn } from "@/shared/lib/cn";

/**
 * A schematic: the board to draw it on (or its code). The board is always there — its grid, the
 * drawing — and its tools fade in while the pointer is over it.
 */
export function SchematicCell({ cell, update, library, simulate, running }: {
  cell: Extract<Cell, { type: "schematic" }>;
  update: (patch: Partial<Cell>) => void;
  library: SymbolLibrary;
  simulate: (schematic?: SchematicData) => void;
  running: boolean;
}) {
  const { t } = useTranslation("notebook");
  const empty = !cell.schematic.elements.length;
  const pdf = usePdf();
  const printed = pdf.results && !cell.stale ? cell.results : undefined; // values on the drawing, if the PDF has them
  const view: SchematicView = cell.view === "code" ? "code" : "schematic";
  // the code view: `generated` is the drawing as code, `source` what is in the editor now
  const [source, setSource] = useState<string | null>(null);
  const [generated, setGenerated] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // the drawing `source` describes: the code is written anew only after the drawing was edited
  // on the board — never just because it ran, so the way someone wrote it stays
  const writtenFor = useRef<SchematicData | null>(null);
  // the board's view survives the trips to the code view; coming back, the board has the keyboard
  const camera = useRef<Camera | null>(null);
  const focusBoard = useRef(false);

  const load = async () => {
    if (source !== null && writtenFor.current === cell.schematic) return;
    const code = await kernel.code(cell.schematic, cell.name);
    writtenFor.current = cell.schematic;
    setSource(code);
    setGenerated(code);
    setError(null);
  };
  // opened in the code view (saved like that): show the code once Python is up
  useEffect(() => {
    if (view === "code" && source === null) kernel.ready.then(load).catch((e) => setError(String(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view]);

  /** The drawing, with the edited code applied (null: the code has an error, shown). */
  const applied = async (): Promise<SchematicData | null> => {
    if (source === null || source === generated) return cell.schematic;
    const back = await kernel.fromCode(source, cell.name, cell.schematic);
    if ("error" in back) {
      setError(back.error);
      return null;
    }
    setError(null);
    writtenFor.current = back.schematic;
    setGenerated(source); // applied: the code in the editor is what the drawing is now
    update({ schematic: back.schematic, ...(cell.results ? { stale: true } : {}) });
    return back.schematic;
  };

  const switchTo = async (next: SchematicView) => {
    if (next === view || busy) return;
    setBusy(true);
    try {
      await kernel.ready;
      if (next === "code") {
        await load();
        update({ view: "code" });
      } else if (await applied()) { // leaving the code: what was edited there first
        focusBoard.current = true;
        update({ view: "schematic" });
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const run = async () => {
    if (view === "schematic") return simulate();
    setBusy(true);
    try {
      const schematic = await applied();
      if (schematic) simulate(schematic);
    } finally {
      setBusy(false);
    }
  };

  const name = <NameBox name={cell.name} onRename={(n) => update({ name: n })} />;
  const actions = <ViewSwitch view={view} onSwitch={switchTo} busy={busy} />;

  // the results are up to date: the run button rests until something changes
  const done = cell.results !== undefined && !cell.stale && !(view === "code" && source !== generated);
  const problems = !cell.stale && cell.problems?.length ? <Problems problems={cell.problems} below={view === "code"} /> : null;

  return (
    // schematic-cell: the board's islands (legacy.css, the schematic's) fade in while the pointer is over it
    <div className="schematic-cell flex gap-2 items-start">
      <RunButton run={run} running={running || busy} done={done || empty} eager icon={<Flash />} label={t("schematic.run")} />
      <div className="flex-1 min-w-0">
      {view === "schematic" ? (
        <SchematicEditor
          value={cell.schematic}
          onChange={(schematic) => update({ schematic, ...(cell.results ? { stale: true } : {}) })}
          library={library}
          results={cell.stale ? undefined : cell.results}
          topLeft={name}
          topRight={actions}
          status={problems}
          camera={camera}
          autoFocus={focusBoard.current}
        />
      ) : (
        <div className="board h-auto min-h-50 p-2.5 flex flex-col gap-2.5">
          <div className="flex items-center gap-2">
            <div className="island static">{name}</div>
            <span className="flex-1" />
            {problems && <div className="island static status relative">{problems}</div>}
            <div className="island static">{actions}</div>
          </div>
          <div className={editorFrame} onKeyDownCapture={runOnShiftEnter(run)}>
            {source === null
              ? <p className="m-2 text-muted">{t("schematic.toCode")}</p>
              : <CodeEditor value={source} onChange={setSource} minHeight={120} />}
          </div>
          {error && <pre data-output="error" className={cn(errorBox, "text-[14px]")}>{error}</pre>}
        </div>
      )}
      {/* the PDF shows the circuit as drawn; results belong to code cells: schematic(układ1, sol) */}
      <PdfDrawing value={cell.schematic} library={library} results={printed} />
      {cell.results && Object.keys(cell.results).length > 0 && (
        <ResultsTable results={cell.results} stale={!!cell.stale} />
      )}
      </div>
    </div>
  );
}
