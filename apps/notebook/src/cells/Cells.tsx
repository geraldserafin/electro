import { useEffect, useState } from "react";
import { CodeIcon, Play, SchematicIcon } from "../icons";
import { kernel } from "../python/kernel";
import { PrintDrawing, SchematicEditor } from "../schematic/Editor";
import type { Cell, SchematicData, SymbolLibrary } from "../types";
import { CodeEditor } from "./CodeEditor";
import { Markdown } from "./Markdown";
import { Outputs } from "./Outputs";

type Update = (patch: Partial<Cell>) => void;

export function MarkdownCell({ cell, update }: { cell: Extract<Cell, { type: "markdown" }>; update: Update }) {
  const [editing, setEditing] = useState(cell.source === "");
  if (!editing)
    return (
      <div className="markdown-view" onDoubleClick={() => setEditing(true)} title="Dwuklik, żeby edytować">
        <Markdown source={cell.source || "*Pusty tekst — kliknij dwukrotnie, żeby pisać.*"} />
      </div>
    );
  return (
    <div className="markdown-edit">
      <textarea
        className="markdown-source"
        autoFocus
        value={cell.source}
        rows={Math.max(3, cell.source.split("\n").length + 1)}
        placeholder="Tekst w Markdown, wzory w $...$ — Shift+Enter kończy edycję"
        onChange={(e) => update({ source: e.target.value })}
        onBlur={() => setEditing(false)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && e.shiftKey) {
            e.preventDefault();
            setEditing(false);
          }
        }}
      />
      <div className="markdown-preview"><Markdown source={cell.source} /></div>
    </div>
  );
}

/** Colab-style gutter: a round run button that shows [n] when the cell has run. */
function RunButton({ run, running, label, execution }: {
  run: () => void; running: boolean; label: string; execution?: number;
}) {
  return (
    <div className="gutter no-print">
      <button className={`run ${running ? "running" : ""}`} onClick={run} disabled={running} title={label} aria-label={label}>
        <Play />
      </button>
      {execution !== undefined && !running && <span className="execution">[{execution}]</span>}
    </div>
  );
}

export function CodeCell({ cell, update, run, running }: {
  cell: Extract<Cell, { type: "code" }>; update: Update; run: () => void; running: boolean;
}) {
  return (
    <div className="code-cell">
      <RunButton run={run} running={running} label="Uruchom komórkę (Shift+Enter)" execution={cell.execution} />
      <div className="cell-body">
        <div
          className="code-editor"
          onKeyDownCapture={(e) => {
            if (e.key === "Enter" && e.shiftKey) {
              e.preventDefault();
              e.stopPropagation();
              run();
            }
          }}
        >
          <CodeEditor value={cell.source} onChange={(source) => update({ source })} />
        </div>
        <Outputs outputs={cell.outputs} />
      </div>
    </div>
  );
}

/** Schemat | Kod: the two views of a schematic cell. */
function ViewSwitch({ view, onSwitch, busy }: { view: "schematic" | "code"; onSwitch: (v: "schematic" | "code") => void; busy: boolean }) {
  return (
    <div className="view-switch" role="tablist" aria-label="Widok komórki">
      <button role="tab" aria-selected={view === "schematic"} className={view === "schematic" ? "on" : ""}
              disabled={busy} onClick={() => onSwitch("schematic")} title="Rysunek schematu">
        <SchematicIcon /> Schemat
      </button>
      <button role="tab" aria-selected={view === "code"} className={view === "code" ? "on" : ""}
              disabled={busy} onClick={() => onSwitch("code")} title="Ten sam układ jako kod electro — można go edytować">
        <CodeIcon /> Kod
      </button>
    </div>
  );
}

export function SchematicCell({ cell, update, library, toCell, simulate, running }: {
  cell: Extract<Cell, { type: "schematic" }>;
  update: Update;
  library: SymbolLibrary;
  toCell: (source: string) => void;
  simulate: (schematic?: SchematicData) => void;
  running: boolean;
}) {
  const empty = !cell.schematic.elements.length;
  const view = cell.view ?? "schematic";
  // the code view: `generated` is the drawing as code, `source` what is in the editor now
  const [source, setSource] = useState<string | null>(null);
  const [generated, setGenerated] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    const code = await kernel.code(cell.schematic, cell.name);
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
    update({ schematic: back.schematic, ...(cell.results ? { stale: true } : {}) });
    return back.schematic;
  };

  const switchTo = async (next: "schematic" | "code") => {
    if (next === view || busy) return;
    setBusy(true);
    try {
      await kernel.ready;
      if (next === "code") {
        await load();
        update({ view: "code" });
      } else if (await applied()) {
        setSource(null);
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
      if (schematic) {
        const code = await kernel.code(schematic, cell.name); // the code as the new drawing writes it
        setSource(code);
        setGenerated(code);
        simulate(schematic);
      }
    } finally {
      setBusy(false);
    }
  };

  const name = (
    <label className="schematic-name" title="Pod tą nazwą kod widzi schemat: schemat(&quot;…&quot;)">
      <code>schemat("</code>
      <input value={cell.name} onChange={(e) => update({ name: e.target.value })} spellCheck={false} />
      <code>")</code>
    </label>
  );
  const actions = (
    <>
      <ViewSwitch view={view} onSwitch={switchTo} busy={busy} />
      <button className="primary" onClick={run} disabled={(empty && view === "schematic") || running || busy}
              title="Policz prądy i napięcia">
        <Play /> {running ? "Liczę…" : "Symuluj"}
      </button>
    </>
  );

  return (
    <div className="schematic-cell">
      {view === "schematic" ? (
        <SchematicEditor
          value={cell.schematic}
          onChange={(schematic) => update({ schematic, ...(cell.results ? { stale: true } : {}) })}
          library={library}
          results={cell.stale ? undefined : cell.results}
          topLeft={name}
          topRight={actions}
        />
      ) : (
        <div className="board code-view">
          <div className="code-view-bar">
            <div className="island static">{name}</div>
            <span className="spacer" />
            <button className="ghost" onClick={() => source && toCell(source)} disabled={!source}
                    title="Wstaw ten kod pod spodem jako zwykłą komórkę z kodem">
              Kopiuj do komórki
            </button>
            <div className="island static">{actions}</div>
          </div>
          <div className="code-editor"
               onKeyDownCapture={(e) => {
                 if (e.key === "Enter" && e.shiftKey) {
                   e.preventDefault();
                   e.stopPropagation();
                   run();
                 }
               }}>
            {source === null
              ? <p className="code-view-wait">Zamieniam schemat na kod…</p>
              : <CodeEditor value={source} onChange={setSource} />}
          </div>
          {error
            ? <pre className="output-error code-view-note">{error}</pre>
            : <p className="code-view-note">
                Zmiany w kodzie wracają na schemat po przełączeniu na „Schemat” (albo Symuluj / Shift+Enter) —
                wtedy schemat układa się na nowo.
              </p>}
        </div>
      )}
      <PrintDrawing value={cell.schematic} library={library} results={cell.stale ? undefined : cell.results} />
      <div className="sim-bar no-print">
        <label>
          Dane pomiarowe
          <input
            value={cell.data ?? ""}
            placeholder="dla niewiadomych, np. I_A_1 = 0; U_R_2 = 4"
            spellCheck={false}
            onChange={(e) => update({ data: e.target.value, ...(cell.results ? { stale: true } : {}) })}
            onKeyDown={(e) => e.key === "Enter" && run()}
          />
        </label>
      </div>
      {cell.outputs && cell.outputs.length > 0 && (
        <div className={cell.stale ? "stale" : ""}>
          {cell.stale && <p className="stale-note">Schemat albo dane się zmieniły — kliknij „Symuluj”, żeby przeliczyć.</p>}
          <Outputs outputs={cell.outputs} />
        </div>
      )}
    </div>
  );
}
