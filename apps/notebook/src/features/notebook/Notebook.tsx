// One note, edited: its cells, running them, and saving it to the notes server as it changes.
// The page (pages/NotePage.tsx) reads the note by its address and hands it over.
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { ExportDialog, PdfContext, pdfOf, warmUpWhenIdle, type PdfSettings } from "@/features/pdf-export";
import { kernel, usePython } from "@/features/python";
import { SyncNotice, useNoteSync } from "@/features/notes";
import { library } from "@/features/schematic";
import { LanguageButton } from "@/features/language";
import { ThemeButton } from "@/features/theme";
import { newCell } from "@/shared/model/cells";
import type { Cell, CellType, Notebook as NotebookData, SchematicData } from "@/shared/model/types";
import { Back, Bolt, Down, Export, OutlineIcon, Plus, RunAll, Trash, Up } from "@/shared/ui/icons";
import { CodeCell, MarkdownCell, SchematicCell } from "./cells/Cells";
import { Outline } from "./Outline";
import { TitleBox } from "./TitleBox";

/**
 * ``initial``/``revision``: the note as read from the server; ``reload``: read it again (after a
 * conflict, to take the server's version).
 */
export function Notebook({ initial, revision, reload, onSaved }: {
  initial: NotebookData; revision: number | null; reload: () => void;
  onSaved?: (slug: string) => void; // after each save: the note's address (a new title may change it)
}) {
  const [notebook, setNotebook] = useState<NotebookData>(initial);
  const python = usePython();
  const [running, setRunning] = useState<Set<string>>(new Set());
  const [focused, setFocused] = useState<string | null>(null);
  const executions = useRef(0);
  const sync = useNoteSync(notebook, revision, reload, onSaved);
  const latest = useRef(notebook);
  latest.current = notebook;
  const ready = python.kind === "ready";
  const [outline, setOutline] = useOutlineOpen();
  const [exporting, setExporting] = useState(false);
  const pdf = pdfOf(notebook.settings);
  const setPdf = (patch: Partial<PdfSettings>) =>
    setNotebook((nb) => ({ ...nb, settings: { ...nb.settings, pdf: { ...pdfOf(nb.settings), ...patch } } }));
  const setTitle = (title: string) => setNotebook({ ...latest.current, title });

  // each note starts with a clean Python: variables of another note do not leak into this one
  useEffect(() => {
    void kernel.ready.then(() => kernel.reset());
  }, []);

  // the PDF's Typst loads in the background once Python is up (not to slow it down): the first
  // export shows its pages at once
  useEffect(() => (ready ? warmUpWhenIdle() : undefined), [ready]);

  // Ctrl+P (⌘P) exports: the PDF is set by Typst, not printed from the page
  useEffect(() => {
    const print = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && !e.altKey && e.key.toLowerCase() === "p") {
        e.preventDefault();
        setExporting(true);
      }
    };
    window.addEventListener("keydown", print);
    return () => window.removeEventListener("keydown", print);
  }, []);

  const setCells = (fn: (cells: Cell[]) => Cell[]) => setNotebook((nb) => ({ ...nb, cells: fn(nb.cells) }));
  const update = (id: string, patch: Partial<Cell>) =>
    setCells((cells) => cells.map((c) => (c.id === id ? ({ ...c, ...patch } as Cell) : c)));
  const insert = (index: number, type: CellType) => {
    const cell = newCell(type);
    if (cell.type === "schematic") cell.name = freeName(latest.current.cells);
    setCells((cells) => [...cells.slice(0, index), cell, ...cells.slice(index)]);
    setFocused(cell.id);
  };
  const remove = (id: string) => setCells((cells) => cells.filter((c) => c.id !== id));
  const move = (index: number, by: number) =>
    setCells((cells) => {
      const target = index + by;
      if (target < 0 || target >= cells.length) return cells;
      const next = [...cells];
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });

  const schematics = (): Record<string, SchematicData> =>
    Object.fromEntries(
      latest.current.cells.flatMap((c) => (c.type === "schematic" ? [[c.name, c.schematic] as const] : [])),
    );

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
        const outputs = await kernel.run(cell.source, schematics());
        update(id, { outputs, execution: ++executions.current });
      } catch (error) {
        update(id, { outputs: [{ type: "error", data: String(error) }] });
      }
    });
  };

  /** ``schematic``: the drawing to simulate, when it was just changed (the cell's state lags behind). */
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



  return (
    <div className="notebook"
         // a click outside every cell (and the app's islands) leaves the cell being worked on
         onPointerDownCapture={(e) => {
           // (the export dialog is a portal: its clicks bubble here too, and are not outside)
           if (!(e.target as Element).closest(".cell, .float, .float-group, .note-nav, [data-notice], .export-backdrop")) setFocused(null);
         }}>
      {/* left: the way back and the app (as on the home screen), under it a sidebar — the note's
          title and its sections; right: run, PDF */}
      <div className="float-group top-left">
        <Link className="float icon-button" to="/" title="Wszystkie notatki" aria-label="Wszystkie notatki"><Back /></Link>
        <div className="float">
          <span className="brand"><Bolt /></span>
          <span className="app-name">electro</span>
        </div>
        <button className={`float icon-button ${outline ? "open" : ""}`} onClick={() => setOutline(!outline)} aria-pressed={outline}
                title={outline ? "Schowaj spis treści" : "Spis treści"} aria-label="Spis treści">
          <OutlineIcon />
        </button>
      </div>
      <aside className={`note-nav ${outline ? "open" : ""}`} inert={!outline}>
        <div className="note-nav-head">
          <TitleBox title={notebook.title} onChange={setTitle} />
        </div>
        <Outline cells={notebook.cells} />
      </aside>
      <div className="float-group top-right">
        <button className={`float icon-button ${ready ? "" : "waiting"}`} onClick={runAll} disabled={!ready}
                title={ready ? "Uruchom wszystko" : python.text} aria-label="Uruchom wszystko"><RunAll /></button>
        <button className="float icon-button" onClick={() => setExporting(true)} title="Eksport do PDF" aria-label="Eksport PDF">
          <Export />
        </button>
        <LanguageButton />
        <ThemeButton />
      </div>
      <SyncNotice state={sync.state} onKeepMine={sync.keepMine} onTakeTheirs={sync.takeTheirs} />
      {exporting && (
        <ExportDialog notebook={notebook} pdf={pdf} onChange={setPdf}
                      onCode={(codeInPdf) => setNotebook((nb) => ({ ...nb, settings: { ...nb.settings, codeInPdf } }))}
                      onClose={() => setExporting(false)} />
      )}

      <PdfContext.Provider value={pdf}>
      <main className={`appear ${outline ? "with-nav" : ""}`}>
        {/* the title is the note's first heading too (and the PDF's) */}
        <input className="doc-title" value={notebook.title} placeholder="Bez tytułu" aria-label="Tytuł"
               spellCheck={false} onChange={(e) => setTitle(e.target.value)} />
        <AddRow onAdd={(type) => insert(0, type)} />
        {notebook.cells.map((cell, index) => (
          <section
            key={cell.id}
            id={`cell-${cell.id}`}
            className={`cell cell-${cell.type} ${focused === cell.id ? "focused" : ""}`}
            onFocusCapture={() => setFocused(cell.id)}
            onPointerDownCapture={() => setFocused(cell.id)}
          >
            <div className="cell-tools">
              <button onClick={() => move(index, -1)} title="W górę" aria-label="W górę"><Up /></button>
              <button onClick={() => move(index, 1)} title="W dół" aria-label="W dół"><Down /></button>
              <button onClick={() => remove(cell.id)} title="Usuń komórkę" aria-label="Usuń komórkę"><Trash /></button>
            </div>
            {cell.type === "markdown" && <MarkdownCell cell={cell} update={(p) => update(cell.id, p)} />}
            {cell.type === "code" && (
              <CodeCell cell={cell} update={(p) => update(cell.id, p)} run={() => run(cell.id)}
                        running={running.has(cell.id)} />
            )}
            {cell.type === "schematic" && (
              <SchematicCell cell={cell} update={(p) => update(cell.id, p)} library={library}
                             simulate={(s) => simulate(cell.id, s)}
                             running={running.has(cell.id)} />
            )}
            <AddRow onAdd={(type) => insert(index + 1, type)} />
          </section>
        ))}
        {!notebook.cells.length && <p className="empty">Pusty notatnik — dodaj pierwszą komórkę przyciskami powyżej.</p>}
      </main>
      </PdfContext.Provider>
    </div>
  );
}

const OUTLINE_KEY = "electro-outline";

/** Is the table of contents open: as last left in this browser; at first, on wide screens. */
function useOutlineOpen(): [boolean, (open: boolean) => void] {
  const [open, setOpen] = useState(() => {
    try {
      const saved = localStorage.getItem(OUTLINE_KEY);
      if (saved !== null) return saved === "1";
    } catch {
      // no storage: the default
    }
    return window.innerWidth >= 1200;
  });
  const set = (next: boolean) => {
    setOpen(next);
    try {
      localStorage.setItem(OUTLINE_KEY, next ? "1" : "0");
    } catch {
      // not remembered — fine
    }
  };
  return [open, set];
}

/** "Układ 1", "Układ 2", …: the first name no schematic has yet. */
function freeName(cells: Cell[]): string {
  const taken = new Set(cells.flatMap((c) => (c.type === "schematic" ? [c.name] : [])));
  let n = 1;
  while (taken.has(`Układ ${n}`)) n++;
  return `Układ ${n}`;
}


function AddRow({ onAdd }: { onAdd: (type: CellType) => void }) {
  return (
    <div className="add-row">
      <button onClick={() => onAdd("code")} title="Dodaj komórkę z kodem"><Plus /> Kod</button>
      <button onClick={() => onAdd("markdown")} title="Dodaj komórkę z tekstem"><Plus /> Tekst</button>
      <button onClick={() => onAdd("schematic")} title="Dodaj schemat"><Plus /> Schemat</button>
    </div>
  );
}
