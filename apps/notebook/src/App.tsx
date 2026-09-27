import { useEffect, useRef, useState, type ReactNode } from "react";
import { CodeCell, MarkdownCell, SchematicCell } from "./cells/Cells";
import { Bolt, Down, Export, More, Plus, RunAll, Trash, Up } from "./icons";
import { copyOf } from "./format";
import { kernel } from "./python/kernel";
import { download, load, newCell, save, upload } from "./storage";
import symbols from "./schematic/symbols.json";
import type { Cell, CellType, Notebook, SchematicData, SymbolLibrary } from "./types";

// generated from electro_render.symbol_library() (scripts/make_symbols.py), so drawings
// show before Python has loaded
const library = symbols as unknown as SymbolLibrary;

type Status = "loading" | "ready" | "error";

/** Every notebook in examples/ shows up in the ⋯ menu (and opens with ?przyklad=<name>). */
const EXAMPLE_FILES = import.meta.glob<Notebook>("../examples/*.electro.json", { eager: true, import: "default" });
const EXAMPLES = Object.values(EXAMPLE_FILES);

/** ?przyklad=nieznane-i-dziury replaces the current notebook with that example. */
function fromAddress(): Notebook | null {
  const params = new URLSearchParams(location.search);
  const name = params.get("przyklad");
  if (!name) return null;
  params.delete("przyklad");
  history.replaceState(null, "", location.pathname + (params.size ? `?${params}` : ""));
  const found = Object.entries(EXAMPLE_FILES).find(([path]) => path.endsWith(`/${name}.electro.json`));
  return found ? copyOf(found[1]) : null;
}

export function App() {
  const [notebook, setNotebook] = useState<Notebook>(() => fromAddress() ?? load());
  const [status, setStatus] = useState<Status>("loading");
  const [statusText, setStatusText] = useState("Uruchamiam Pythona…");
  const [running, setRunning] = useState<Set<string>>(new Set());
  const [focused, setFocused] = useState<string | null>(null);
  const executions = useRef(0);
  const fileInput = useRef<HTMLInputElement>(null);
  const latest = useRef(notebook);
  latest.current = notebook;

  useEffect(() => {
    kernel.ready
      .then(() => {
        setStatus("ready");
        setStatusText("Python gotowy");
      })
      .catch((error: Error) => {
        setStatus("error");
        setStatusText(`Python się nie uruchomił: ${error.message}`);
      });
  }, []);

  // save at most 400 ms after a change — not 400 ms after the last one, which never comes while
  // "run all" keeps adding outputs
  const saving = useRef<number | null>(null);
  useEffect(() => {
    if (saving.current === null)
      saving.current = window.setTimeout(() => {
        saving.current = null;
        save(latest.current);
      }, 400);
  }, [notebook]);
  useEffect(() => () => { if (saving.current !== null) save(latest.current); }, []);

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

  const resetKernel = async () => {
    await kernel.reset();
    executions.current = 0;
    setCells((cells) => cells.map((c) => (c.type === "code" ? { ...c, outputs: [], execution: undefined } : c)));
  };

  const open = async (file: File | undefined) => {
    if (!file) return;
    try {
      setNotebook(await upload(file));
    } catch (error) {
      alert(String(error));
    }
  };

  const openExample = (example: Notebook) => {
    if (confirm("Otworzyć przykład? Bieżący notatnik zostanie zastąpiony (zapisz go wcześniej: ⋯ → Zapisz plik)."))
      setNotebook(copyOf(example));
  };

  return (
    <div className={`notebook ${notebook.settings.codeInPdf ? "" : "hide-code-in-print"}`}>
      {/* one line: logo, title — Python's state, run all, PDF, and the rest under "⋯" */}
      <header className="appbar no-print">
        <div className="brand" title="electro — notatnik elektroniki"><Bolt /></div>
        <input className="title" value={notebook.title} placeholder="Bez tytułu" aria-label="Tytuł notatnika"
               onChange={(e) => setNotebook({ ...notebook, title: e.target.value })} />
        <div className={`status ${status}`} title={statusText} role="status" aria-label={statusText}>
          <span className="dot" /> Python
        </div>
        <button className="icon-button" onClick={runAll} disabled={status !== "ready"}
                title="Uruchom wszystko" aria-label="Uruchom wszystko"><RunAll /></button>
        <button className="icon-button" onClick={() => window.print()} title="Eksport do PDF" aria-label="Eksport PDF">
          <Export />
        </button>
        <Menu label={<More />} title="Więcej" right>
          <button onClick={() => fileInput.current?.click()}>Otwórz plik…</button>
          <button onClick={() => download(notebook)}>Zapisz plik</button>
          <hr />
          {EXAMPLES.map((example, i) => (
            <button key={i} onClick={() => openExample(example)}>Przykład: {example.title}</button>
          ))}
          <hr />
          <label className="check">
            <input type="checkbox" checked={notebook.settings.codeInPdf}
                   onChange={(e) => setNotebook({ ...notebook, settings: { ...notebook.settings, codeInPdf: e.target.checked } })} />
            pokazuj kod w PDF
          </label>
          <button onClick={resetKernel} disabled={status !== "ready"}>Wyczyść pamięć Pythona</button>
        </Menu>
        <input ref={fileInput} type="file" accept=".json" hidden onChange={(e) => open(e.target.files?.[0])} />
      </header>

      <main>
        <AddRow onAdd={(type) => insert(0, type)} />
        {notebook.cells.map((cell, index) => (
          <section
            key={cell.id}
            className={`cell cell-${cell.type} ${focused === cell.id ? "focused" : ""}`}
            onFocusCapture={() => setFocused(cell.id)}
            onPointerDownCapture={() => setFocused(cell.id)}
          >
            <div className="cell-tools no-print">
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
    </div>
  );
}

/** "Układ 1", "Układ 2", …: the first name no schematic has yet. */
function freeName(cells: Cell[]): string {
  const taken = new Set(cells.flatMap((c) => (c.type === "schematic" ? [c.name] : [])));
  let n = 1;
  while (taken.has(`Układ ${n}`)) n++;
  return `Układ ${n}`;
}

function Menu({ label, title, right, children }: { label: ReactNode; title?: string; right?: boolean; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (event: PointerEvent) => {
      if (!ref.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", close);
    return () => document.removeEventListener("pointerdown", close);
  }, [open]);
  return (
    <div className={`menu ${right ? "right" : ""}`} ref={ref}>
      <button className={`icon-button ${open ? "open" : ""}`} onClick={() => setOpen(!open)} aria-haspopup="menu"
              aria-expanded={open} title={title} aria-label={title}>
        {label}
      </button>
      {open && (
        <div className="menu-items" role="menu" onClick={(e) => (e.target as HTMLElement).tagName === "BUTTON" && setOpen(false)}>
          {children}
        </div>
      )}
    </div>
  );
}

function AddRow({ onAdd }: { onAdd: (type: CellType) => void }) {
  return (
    <div className="add-row no-print">
      <button onClick={() => onAdd("code")} title="Dodaj komórkę z kodem"><Plus /> Kod</button>
      <button onClick={() => onAdd("markdown")} title="Dodaj komórkę z tekstem"><Plus /> Tekst</button>
      <button onClick={() => onAdd("schematic")} title="Dodaj schemat"><Plus /> Schemat</button>
    </div>
  );
}
