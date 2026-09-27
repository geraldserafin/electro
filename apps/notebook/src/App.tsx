import { useEffect, useRef, useState } from "react";
import { CodeCell, MarkdownCell, SchematicCell } from "./cells/Cells";
import { kernel } from "./python/kernel";
import { download, load, newCell, save, upload } from "./storage";
import type { Cell, CellType, Notebook, SchematicData, SymbolLibrary } from "./types";

type Status = "loading" | "ready" | "error";

export function App() {
  const [notebook, setNotebook] = useState<Notebook>(load);
  const [library, setLibrary] = useState<SymbolLibrary | null>(null);
  const [status, setStatus] = useState<Status>("loading");
  const [statusText, setStatusText] = useState("Ładowanie Pythona (Pyodide)…");
  const [running, setRunning] = useState<Set<string>>(new Set());
  const fileInput = useRef<HTMLInputElement>(null);
  const latest = useRef(notebook);
  latest.current = notebook;

  useEffect(() => {
    kernel.ready
      .then(() => kernel.symbols())
      .then((lib) => {
        setLibrary(lib);
        setStatus("ready");
        setStatusText("Python gotowy");
      })
      .catch((error: Error) => {
        setStatus("error");
        setStatusText(`Nie udało się uruchomić Pythona: ${error.message}`);
      });
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => save(notebook), 400);
    return () => clearTimeout(timer);
  }, [notebook]);

  const setCells = (fn: (cells: Cell[]) => Cell[]) => setNotebook((nb) => ({ ...nb, cells: fn(nb.cells) }));
  const update = (id: string, patch: Partial<Cell>) =>
    setCells((cells) => cells.map((c) => (c.id === id ? ({ ...c, ...patch } as Cell) : c)));
  const insert = (index: number, type: CellType) =>
    setCells((cells) => [...cells.slice(0, index), newCell(type), ...cells.slice(index)]);
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

  const run = async (id: string) => {
    const cell = latest.current.cells.find((c) => c.id === id);
    if (!cell || cell.type !== "code") return;
    setRunning((r) => new Set(r).add(id));
    try {
      await kernel.ready;
      update(id, { outputs: await kernel.run(cell.source, schematics()) });
    } catch (error) {
      update(id, { outputs: [{ type: "error", data: String(error) }] });
    } finally {
      setRunning((r) => {
        const next = new Set(r);
        next.delete(id);
        return next;
      });
    }
  };

  const runAll = async () => {
    for (const cell of latest.current.cells) if (cell.type === "code") await run(cell.id);
  };

  const showCode = async (index: number, cell: Extract<Cell, { type: "schematic" }>) => {
    try {
      const source = await kernel.code(cell.schematic, cell.name);
      setCells((cells) => [...cells.slice(0, index + 1), { ...newCell("code"), source } as Cell, ...cells.slice(index + 1)]);
    } catch (error) {
      alert(`Nie udało się zamienić schematu na kod: ${error}`);
    }
  };

  const resetKernel = async () => {
    await kernel.reset();
    setCells((cells) => cells.map((c) => (c.type === "code" ? { ...c, outputs: [] } : c)));
  };

  const open = async (file: File | undefined) => {
    if (!file) return;
    try {
      setNotebook(await upload(file));
    } catch (error) {
      alert(String(error));
    }
  };

  return (
    <div className={`notebook ${notebook.codeInPdf ? "" : "hide-code-in-print"}`}>
      <header className="toolbar no-print">
        <span className={`status ${status}`} title={statusText}>● {statusText}</span>
        <span className="spacer" />
        <button onClick={runAll} disabled={status !== "ready"}>▶ Uruchom wszystko</button>
        <button onClick={resetKernel} disabled={status !== "ready"}>Wyczyść pamięć</button>
        <button onClick={() => fileInput.current?.click()}>Otwórz…</button>
        <button onClick={() => download(notebook)}>Zapisz plik</button>
        <label className="check">
          <input type="checkbox" checked={notebook.codeInPdf}
                 onChange={(e) => setNotebook({ ...notebook, codeInPdf: e.target.checked })} />
          kod w PDF
        </label>
        <button className="primary" onClick={() => window.print()}>Eksport PDF</button>
        <input ref={fileInput} type="file" accept=".json" hidden onChange={(e) => open(e.target.files?.[0])} />
      </header>

      <main>
        <input className="title" value={notebook.title} placeholder="Tytuł"
               onChange={(e) => setNotebook({ ...notebook, title: e.target.value })} />
        <AddRow onAdd={(type) => insert(0, type)} />
        {notebook.cells.map((cell, index) => (
          <section key={cell.id} className={`cell cell-${cell.type}`}>
            <div className="cell-tools no-print">
              <button onClick={() => move(index, -1)} title="W górę">↑</button>
              <button onClick={() => move(index, 1)} title="W dół">↓</button>
              <button onClick={() => remove(cell.id)} title="Usuń komórkę">✕</button>
            </div>
            {cell.type === "markdown" && <MarkdownCell cell={cell} update={(p) => update(cell.id, p)} />}
            {cell.type === "code" && (
              <CodeCell cell={cell} update={(p) => update(cell.id, p)} run={() => run(cell.id)}
                        running={running.has(cell.id)} />
            )}
            {cell.type === "schematic" && (
              <SchematicCell cell={cell} update={(p) => update(cell.id, p)} library={library}
                             showCode={() => showCode(index, cell)} />
            )}
            <AddRow onAdd={(type) => insert(index + 1, type)} />
          </section>
        ))}
      </main>
    </div>
  );
}

function AddRow({ onAdd }: { onAdd: (type: CellType) => void }) {
  return (
    <div className="add-row no-print">
      <button onClick={() => onAdd("markdown")}>+ Tekst</button>
      <button onClick={() => onAdd("code")}>+ Kod</button>
      <button onClick={() => onAdd("schematic")}>+ Schemat</button>
    </div>
  );
}
