// One note, edited: its cells, running them, and saving it as it changes. The page
// (pages/NotePage.tsx) reads the note by its address and hands it over. A note in chapters
// (shared/model/parts.ts) shows one chapter — a page — at a time, the way to the others under it
// and in the sidebar (its ⋯ menu: the whole note, one page, instead).
import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { AiButton, AiChat } from "@/features/ai";
import { ReadOnlyNotice, SyncNotice, useCreateNote, useNoteSync } from "@/features/notes";
import { ExportDialog, PdfContext, type PdfSettings, pdfOf, warmUpWhenIdle } from "@/features/pdf-export";
import { kernel, usePython } from "@/features/python";
import { libraryFor, PdfDrawing } from "@/features/schematic";
import { SettingsMenu, SymbolsChoice } from "@/features/settings";
import { useTitle } from "@/shared/hooks/useTitle";
import { cn } from "@/shared/lib/cn";
import { newCell } from "@/shared/model/cells";
import { copyOf } from "@/shared/model/format";
import { partMark, partsOf } from "@/shared/model/parts";
import type { Cell, CellType, Notebook as NotebookData, SymbolStandard } from "@/shared/model/types";
import { IslandButton, IslandLink, Islands } from "@/shared/ui/Island";
import { Back, Export, Notes, OutlineIcon, RunAll, ShareIcon } from "@/shared/ui/icons";
import { MenuItem } from "@/shared/ui/Menu";
import { AddRow } from "./AddRow";
import { CellFrame } from "./CellFrame";
import { freeName, moveRange, moveSection } from "./cellList";
import { CodeCell } from "./cells/CodeCell";
import { MarkdownCell } from "./cells/MarkdownCell";
import { SchematicCell } from "./cells/SchematicCell";
import { column } from "./layout";
import { Pager } from "./Parts";
import { Sidebar } from "./Sidebar";
import { useOutlineOpen } from "./useOutlineOpen";
import { usePrintKey } from "./usePrintKey";
import { useRemoved } from "./useRemoved";
import { useRunner } from "./useRunner";

// A cell is drawn again when its own data changes, not whenever the note does (a key typed in
// another cell, the title, a save): its callbacks are made anew each render of the note, but
// they only act on the cell by its id and on the note as it is then, so an older one does the same.
const sameButCallbacks = <P extends object>(a: P, b: P) =>
  (Object.keys(a) as (keyof P)[]).every(
    (k) => a[k] === b[k] || (typeof a[k] === "function" && typeof b[k] === "function"),
  );
const Markdown = memo(MarkdownCell, sameButCallbacks);
const Code = memo(CodeCell, sameButCallbacks);
const Schematic = memo(SchematicCell, sameButCallbacks);
/** This browser's choice: a note in chapters as one long page, not a page a chapter. */
const WHOLE = "electro.wholeNote";

/**
 * ``initial``/``revision``: the note as read from the server; ``reload``: read it again (after a
 * conflict, to take the server's version).
 */
export function Notebook({
  initial,
  revision,
  reload,
  onTitle,
  readOnly = false,
  example = false,
  back,
  onShare,
  embed,
}: {
  initial: NotebookData;
  revision: number | null;
  reload: () => void;
  onTitle?: (title: string) => void; // the title changed (the address shows it)
  readOnly?: boolean; // shared with the user to read: it runs, it is not saved
  example?: boolean; // a lesson (features/examples), read-only too: added to the notes as it is, under its own title
  back: { to: string; label: string }; // the way back: the folder it is in
  onShare?: (notebook: NotebookData) => void; // the user's own: who else has it (and its picture, as it is now)
  embed?: string; // in an <iframe>: no way back, no sidebar, no notice; this link opens it in the app
}) {
  const { t } = useTranslation("notebook");
  const { t: tNotes } = useTranslation("notes");
  const { t: tSharing } = useTranslation("sharing");
  const [notebook, setNotebook] = useState<NotebookData>(initial);
  const latest = useRef(notebook);
  latest.current = notebook;
  useTitle(notebook.title || t("untitled"));
  const python = usePython();
  const ready = python.kind === "ready";
  const [focused, setFocused] = useState<string | null>(null);
  const sync = useNoteSync(notebook, revision, reload, readOnly);
  const create = useCreateNote();
  const copy = async () => {
    // a read-only note, the user's own to change (as it is now, with what they changed here)
    const own = copyOf(latest.current);
    const title = example ? own.title : tNotes("readOnly.copyTitle", { title: own.title || t("untitled") });
    if (!(await create({ ...own, title }))) alert(tNotes("readOnly.copyFailed"));
  };
  useEffect(() => onTitle?.(notebook.title), [notebook.title]); // eslint-disable-line react-hooks/exhaustive-deps
  const [outline, setOutline] = useOutlineOpen();
  const [exporting, setExporting] = useState(false);
  const [chat, setChat] = useState(false); // the assistant, open beside the note (one's own)
  const assistant = !readOnly && !embed;
  const pdf = pdfOf(notebook.settings);
  // the symbols' standard the note draws with (IEC unless it says IEEE)
  const symbols: SymbolStandard = notebook.settings.symbols === "ieee" ? "ieee" : "iec";
  const library = libraryFor(symbols);
  const setPdf = (patch: Partial<PdfSettings>) =>
    setNotebook((nb) => ({ ...nb, settings: { ...nb.settings, pdf: { ...pdfOf(nb.settings), ...patch } } }));
  const setTitle = (title: string) => setNotebook({ ...latest.current, title });

  const setCells = (fn: (cells: Cell[]) => Cell[]) => setNotebook((nb) => ({ ...nb, cells: fn(nb.cells) }));
  const update = (id: string, patch: Partial<Cell>) =>
    setCells((cells) => cells.map((c) => (c.id === id ? ({ ...c, ...patch } as Cell) : c)));
  // its chapters: pages, the one shown (a cell worked on elsewhere brings its chapter up); one long page
  // instead, if this browser's reader would rather (the one read now lit in the outline)
  const [whole, setWhole] = useState(() => {
    try {
      return localStorage.getItem(WHOLE) === "1";
    } catch {
      return false;
    }
  });
  const setWholeKept = (on: boolean) => {
    setWhole(on);
    try {
      localStorage.setItem(WHOLE, on ? "1" : "0");
    } catch {}
  };
  const parts = useMemo(() => partsOf(notebook.cells), [notebook.cells]);
  const paged = !whole && parts.length > 1;
  const [page, setPage] = useState(0);
  const at = Math.min(page, parts.length - 1);
  const part = parts[at]!;
  const go = (n: number) => {
    setPage(n);
    setFocused(null); // (a cell worked on elsewhere would bring its own page back)
    const first = latest.current.cells[parts[n]!.start];
    if (paged || n === 0 || !first) window.scrollTo({ top: 0 });
    else document.getElementById(`cell-${first.id}`)?.scrollIntoView({ block: "start" });
  };
  useEffect(() => {
    const i = focused ? notebook.cells.findIndex((c) => c.id === focused) : -1;
    if (paged && i >= 0 && (i < part.start || i >= part.end))
      setPage(parts.findIndex((p) => i >= p.start && i < p.end));
  }, [paged, focused, notebook.cells, part, parts]);
  useEffect(() => {
    if (paged || parts.length < 2) return;
    // the chapter read now: the last whose first cell is above a line under the app bar
    const onScroll = () => {
      const cells = latest.current.cells;
      const above = parts.filter((p, i) => {
        const el = i && document.getElementById(`cell-${cells[p.start]?.id}`);
        return !el || el.getBoundingClientRect().top < 140;
      });
      setPage(above.length - 1);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [paged, parts]);
  const shown = paged ? part : { start: 0, end: notebook.cells.length };

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
  const removed = useRemoved(() => latest.current.cells, setCells); // a removed cell comes back with Ctrl/⌘ Z
  /** A new chapter at the note's end: its heading, the start of its page. */
  const addPart = () => {
    const cell = { ...newCell("markdown"), source: `# ${t("part.name", { n: parts.length + 1 })}`, part: {} } as Cell;
    setCells((cells) => [...cells, cell]);
    setPage(parts.length);
    setFocused(cell.id);
  };

  return (
    <div
      className="animate-[fade-in_0.25s_ease_both]" // read from this browser in a moment: it comes in, no placeholder before it
      // a click outside every cell (and the app's islands, the notice, the dialog) leaves the cell
      // being worked on (the export dialog is a portal: its clicks bubble here too, and are not outside)
      onPointerDownCapture={(e) => {
        if (!(e.target as Element).closest("[data-cell], [data-keep-focus]")) setFocused(null);
      }}
    >
      {/* left: the way back, and the sidebar's switch (the note's title and its sections);
          right: run, PDF, the settings (theme, language) */}
      {embed ? (
        <Islands side="left">
          <a
            href={embed}
            target="_blank"
            rel="noreferrer"
            className="flex items-center h-10 px-3.5 rounded-xl border border-line bg-island shadow-tools text-[14px] hover:bg-hover"
          >
            {tSharing("openInApp")} ↗
          </a>
        </Islands>
      ) : (
        <Islands side="left">
          <IslandLink to={back.to} title={back.label} aria-label={back.label}>
            <Back />
          </IslandLink>
          <IslandButton
            on={outline}
            onClick={() => setOutline(!outline)}
            aria-pressed={outline}
            title={outline ? t("hideOutline") : t("outline")}
            aria-label={t("outline")}
          >
            <OutlineIcon />
          </IslandButton>
        </Islands>
      )}
      {!embed && (
        <Sidebar
          open={outline}
          title={notebook.title}
          onTitle={setTitle}
          cells={notebook.cells}
          parts={parts}
          page={at}
          editing={!readOnly}
          onPage={go}
          onMove={(from, until, before) => setCells((cells) => moveSection(cells, from, until, before))}
          onAddPart={addPart}
          onRemove={(n) => removed.remove(notebook.cells[parts[n]!.start]!.id, parts[n]!.end - parts[n]!.start)}
          onMovePart={(n, before) => {
            const p = parts[n]!;
            setCells((cells) => moveRange(cells, p.start, p.end - p.start, parts[before]?.start ?? cells.length));
          }}
          onClose={() => setOutline(false)}
        />
      )}
      <Islands side="right">
        <IslandButton
          waiting={!ready}
          onClick={runAll}
          disabled={!ready}
          title={
            ready
              ? t("runAll")
              : python.kind === "error"
                ? t("python.failed", { error: python.error })
                : t("python.loading")
          }
          aria-label={t("runAll")}
        >
          <RunAll />
        </IslandButton>
        <SettingsMenu
          // the note's own: share it, export it (Ctrl/⌘ P); its symbols among the preferences
          actions={
            <>
              {onShare && (
                <MenuItem icon={<ShareIcon />} onSelect={() => onShare(latest.current)}>
                  {t("share")}
                </MenuItem>
              )}
              <MenuItem
                icon={<Export />}
                shortcut={/Mac|iPhone|iPad/.test(navigator.platform) ? "⌘P" : "Ctrl+P"}
                onSelect={() => setExporting(true)}
              >
                {t("exportPdf")}
              </MenuItem>
              {parts.length > 1 && (
                <MenuItem icon={<Notes />} onSelect={() => setWholeKept(!whole)}>
                  {whole ? t("part.paged") : t("part.whole")}
                </MenuItem>
              )}
            </>
          }
          preferences={
            <SymbolsChoice
              value={symbols}
              onChange={(next) => setNotebook((nb) => ({ ...nb, settings: { ...nb.settings, symbols: next } }))}
            />
          }
        />
      </Islands>
      {embed ? null : readOnly ? (
        <ReadOnlyNotice onCopy={() => void copy()} example={example} />
      ) : (
        <SyncNotice state={sync.state} onKeepMine={sync.keepMine} onTakeTheirs={sync.takeTheirs} />
      )}
      {removed.last && (
        // the last removal: a moment, with the way back
        <div
          role="status"
          className="fixed bottom-5 left-1/2 -translate-x-1/2 z-40 flex items-center gap-3 pl-4 pr-1.5 py-1.5 rounded-xl border border-line bg-paper shadow-menu text-[15px]"
        >
          {removed.last.length > 1 || partMark(removed.last[0]!) ? t("part.removed") : t("cell.removed")}
          <button className="h-8 px-3 rounded-lg font-medium text-accent hover:bg-accent-soft" onClick={removed.undo}>
            {t("cell.undo")}{" "}
            <kbd className="ml-1 font-sans text-[13px] text-faint pointer-coarse:hidden">
              {/Mac|iPhone|iPad/.test(navigator.platform) ? "⌘Z" : "Ctrl+Z"}
            </kbd>
          </button>
        </div>
      )}
      {assistant && (
        <>
          <AiButton open={chat} onToggle={() => setChat(!chat)} />
          <AiChat
            open={chat}
            onClose={() => setChat(false)}
            cells={() => latest.current.cells}
            setCells={(cells) => setCells(() => cells)}
            at={() => {
              const now = latest.current.cells;
              const i = focused ? now.findIndex((c) => c.id === focused) : -1;
              return i < 0 ? now.length : i + 1;
            }}
          />
        </>
      )}
      {exporting && (
        <ExportDialog
          notebook={notebook}
          pdf={pdf}
          onChange={setPdf}
          onCode={(codeInPdf) => setNotebook((nb) => ({ ...nb, settings: { ...nb.settings, codeInPdf } }))}
          onClose={() => setExporting(false)}
        />
      )}

      <PdfContext.Provider value={pdf}>
        <main className={cn("appear", column(outline, chat && assistant))}>
          {/* the title is the note's first heading too (and the PDF's); in line with the cells' text — the
              start's, on pages */}
          {(!paged || at === 0) && (
            <input
              className="block w-full mt-0 mb-4 py-1 pr-2 pl-3 rounded-lg border-none bg-transparent text-[34px] max-sm:text-[26px] font-semibold leading-tight
                          placeholder:text-faint focus:outline-none focus:bg-hover"
              value={notebook.title}
              placeholder={t("untitled")}
              aria-label={t("title")}
              spellCheck={false}
              onChange={(e) => setTitle(e.target.value)}
            />
          )}
          <AddRow onAdd={(type) => insert(shown.start, type)} shown={notebook.cells.length === 0} />
          {notebook.cells.slice(shown.start, shown.end).map((cell, k) => {
            const index = shown.start + k;
            return (
              <CellFrame
                key={cell.id}
                id={cell.id}
                type={cell.type}
                focused={focused === cell.id}
                onFocus={() => setFocused(cell.id)}
                onMoveTo={(before) => setCells((cells) => moveRange(cells, index, 1, before))}
                onRemove={() => removed.remove(cell.id)}
                onAdd={(type) => insert(index + 1, type)}
              >
                {cell.type === "markdown" && <Markdown cell={cell} update={(p) => update(cell.id, p)} />}
                {cell.type === "code" && (
                  <Code
                    cell={cell}
                    update={(p) => update(cell.id, p)}
                    run={() => run(cell.id)}
                    running={running.has(cell.id)}
                  />
                )}
                {cell.type === "schematic" && (
                  <Schematic
                    cell={cell}
                    update={(p) => update(cell.id, p)}
                    library={library}
                    simulate={(s) => simulate(cell.id, s)}
                    running={running.has(cell.id)}
                  />
                )}
              </CellFrame>
            );
          })}
          {/* a touch screen: a cell added at the end, always there (none between the cells: see CellFrame) */}
          {notebook.cells.length > 0 && (
            <div className="hidden pointer-coarse:block mt-8">
              <AddRow shown onAdd={(type) => insert(shown.end, type)} />
            </div>
          )}
          {paged && <Pager parts={parts} page={at} title={notebook.title || t("untitled")} onPage={go} />}
          {/* the other pages' drawings, hidden: the PDF takes every drawing from the page */}
          {paged &&
            notebook.cells.map(
              (c, i) =>
                c.type === "schematic" &&
                (i < shown.start || i >= shown.end) && (
                  <div key={c.id} id={`cell-${c.id}`} aria-hidden>
                    <PdfDrawing value={c.schematic} library={library} />
                  </div>
                ),
            )}
          {!notebook.cells.length && <p className="my-4.5 text-muted text-center">{t("empty")}</p>}
        </main>
      </PdfContext.Provider>
    </div>
  );
}
