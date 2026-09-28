// One note, edited: its cells, running them, and saving it to the notes server as it changes.
// The page (pages/NotePage.tsx) reads the note by its address and hands it over.
import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { SyncNotice, useNoteSync } from "@/features/notes";
import { ExportDialog, PdfContext, pdfOf, warmUpWhenIdle, type PdfSettings } from "@/features/pdf-export";
import { kernel, usePython } from "@/features/python";
import { library } from "@/features/schematic";
import { SettingsMenu } from "@/features/settings";
import { newCell } from "@/shared/model/cells";
import type { Cell, CellType, Notebook as NotebookData } from "@/shared/model/types";
import { Back, Export, OutlineIcon, RunAll } from "@/shared/ui/icons";
import { IslandButton, IslandLink, Islands } from "@/shared/ui/Island";
import { AddRow } from "./AddRow";
import { CellFrame } from "./CellFrame";
import { freeName, moveCell } from "./cellList";
import { CodeCell } from "./cells/CodeCell";
import { MarkdownCell } from "./cells/MarkdownCell";
import { SchematicCell } from "./cells/SchematicCell";
import { column } from "./layout";
import { Sidebar } from "./Sidebar";
import { useOutlineOpen } from "./useOutlineOpen";
import { usePrintKey } from "./usePrintKey";
import { useRunner } from "./useRunner";
import { cn } from "@/shared/lib/cn";

/**
 * ``initial``/``revision``: the note as read from the server; ``reload``: read it again (after a
 * conflict, to take the server's version).
 */
export function Notebook({ initial, revision, reload, onTitle, readOnly = false, back }: {
  initial: NotebookData; revision: number | null; reload: () => void;
  onTitle?: (title: string) => void; // the title changed (the address shows it)
  readOnly?: boolean; // shared with the user to read: it runs, it is not saved
  back: { to: string; label: string }; // the way back: the folder it is in
}) {
  const { t } = useTranslation("notebook");
  const [notebook, setNotebook] = useState<NotebookData>(initial);
  const latest = useRef(notebook);
  latest.current = notebook;
  const python = usePython();
  const ready = python.kind === "ready";
  const [focused, setFocused] = useState<string | null>(null);
  const sync = useNoteSync(notebook, revision, reload, readOnly);
  useEffect(() => onTitle?.(notebook.title), [notebook.title]); // eslint-disable-line react-hooks/exhaustive-deps
  const [outline, setOutline] = useOutlineOpen();
  const [exporting, setExporting] = useState(false);
  const pdf = pdfOf(notebook.settings);
  const setPdf = (patch: Partial<PdfSettings>) =>
    setNotebook((nb) => ({ ...nb, settings: { ...nb.settings, pdf: { ...pdfOf(nb.settings), ...patch } } }));
  const setTitle = (title: string) => setNotebook({ ...latest.current, title });

  const setCells = (fn: (cells: Cell[]) => Cell[]) => setNotebook((nb) => ({ ...nb, cells: fn(nb.cells) }));
  const update = (id: string, patch: Partial<Cell>) =>
    setCells((cells) => cells.map((c) => (c.id === id ? ({ ...c, ...patch } as Cell) : c)));
  const insert = (index: number, type: CellType) => {
    const cell = newCell(type);
    if (cell.type === "schematic") cell.name = freeName(latest.current.cells, (n) => t("schematic.defaultName", { n }));
    setCells((cells) => [...cells.slice(0, index), cell, ...cells.slice(index)]);
    setFocused(cell.id);
  };
  const { running, run, simulate, runAll } = useRunner(latest, update);

  // each note starts with a clean Python: variables of another note do not leak into this one
  useEffect(() => {
    void kernel.ready.then(() => kernel.reset());
  }, []);

  // the PDF's Typst loads in the background once Python is up (not to slow it down): the first
  // export shows its pages at once
  useEffect(() => (ready ? warmUpWhenIdle() : undefined), [ready]);

  usePrintKey(useCallback(() => setExporting(true), []));

  return (
    <div
      // a click outside every cell (and the app's islands, the notice, the dialog) leaves the cell
      // being worked on (the export dialog is a portal: its clicks bubble here too, and are not outside)
      onPointerDownCapture={(e) => {
        if (!(e.target as Element).closest("[data-cell], [data-keep-focus]")) setFocused(null);
      }}>
      {/* left: the way back, and the sidebar's switch (the note's title and its sections);
          right: run, PDF, the settings (theme, language) */}
      <Islands side="left">
        <IslandLink to={back.to} title={back.label} aria-label={back.label}><Back /></IslandLink>
        <IslandButton on={outline} onClick={() => setOutline(!outline)} aria-pressed={outline}
                      title={outline ? t("hideOutline") : t("outline")} aria-label={t("outline")}>
          <OutlineIcon />
        </IslandButton>
      </Islands>
      <Sidebar open={outline} title={notebook.title} onTitle={setTitle} cells={notebook.cells} />
      <Islands side="right">
        <IslandButton waiting={!ready} onClick={runAll} disabled={!ready}
                      title={ready ? t("runAll") : python.kind === "error" ? t("python.failed", { error: python.error }) : t("python.loading")} aria-label={t("runAll")}><RunAll /></IslandButton>
        <IslandButton onClick={() => setExporting(true)} title={t("exportPdf")} aria-label={t("exportPdf")}><Export /></IslandButton>
        <SettingsMenu />
      </Islands>
      <SyncNotice state={sync.state} onKeepMine={sync.keepMine} onTakeTheirs={sync.takeTheirs} />
      {exporting && (
        <ExportDialog notebook={notebook} pdf={pdf} onChange={setPdf}
                      onCode={(codeInPdf) => setNotebook((nb) => ({ ...nb, settings: { ...nb.settings, codeInPdf } }))}
                      onClose={() => setExporting(false)} />
      )}

      <PdfContext.Provider value={pdf}>
      <main className={cn("appear", column(outline))}>
        {/* the title is the note's first heading too (and the PDF's); in line with the cells' text */}
        <input className="block w-full mt-0 mb-1 py-1 pr-2 pl-16.25 rounded-lg border-none bg-transparent text-[34px] font-semibold leading-tight
                          placeholder:text-faint focus:outline-none focus:bg-hover"
               value={notebook.title} placeholder={t("untitled")} aria-label={t("title")}
               spellCheck={false} onChange={(e) => setTitle(e.target.value)} />
        <AddRow onAdd={(type) => insert(0, type)} shown={notebook.cells.length === 0} />
        {notebook.cells.map((cell, index) => (
          <CellFrame key={cell.id} id={cell.id} type={cell.type} focused={focused === cell.id} onFocus={() => setFocused(cell.id)}
                     onMove={(by) => setCells((cells) => moveCell(cells, index, by))}
                     onRemove={() => setCells((cells) => cells.filter((c) => c.id !== cell.id))}
                     onAdd={(type) => insert(index + 1, type)}>
            {cell.type === "markdown" && <MarkdownCell cell={cell} update={(p) => update(cell.id, p)} />}
            {cell.type === "code" && (
              <CodeCell cell={cell} update={(p) => update(cell.id, p)} run={() => run(cell.id)} running={running.has(cell.id)} />
            )}
            {cell.type === "schematic" && (
              <SchematicCell cell={cell} update={(p) => update(cell.id, p)} library={library}
                             simulate={(s) => simulate(cell.id, s)} running={running.has(cell.id)} />
            )}
          </CellFrame>
        ))}
        {!notebook.cells.length && <p className="my-4.5 text-muted text-center">{t("empty")}</p>}
      </main>
      </PdfContext.Provider>
    </div>
  );
}
