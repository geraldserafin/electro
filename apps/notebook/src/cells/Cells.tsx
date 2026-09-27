import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { CodeIcon, Eye, Flash, Pencil, Play, SchematicIcon, WarningIcon } from "../icons";
import { kernel } from "../python/kernel";
import { PrintDrawing, SchematicEditor, type Camera } from "../schematic/Editor";
import type { Cell, ElementResult, Problem, SchematicData, SchematicView, SymbolLibrary } from "../types";
import { CodeEditor } from "./CodeEditor";
import { Markdown } from "./Markdown";
import { Outputs } from "./Outputs";

type Update = (patch: Partial<Cell>) => void;

/**
 * A text cell: the rendered text, or — while editing — its plain Markdown. Clicking the text (or
 * the pencil on the side) edits it; leaving the field (or the eye, Esc, Shift+Enter) shows it.
 */
export function MarkdownCell({ cell, update }: { cell: Extract<Cell, { type: "markdown" }>; update: Update }) {
  const [editing, setEditing] = useState(cell.source === "");
  const field = useRef<HTMLTextAreaElement>(null);
  // the field grows with the text, so the page scrolls, not the field
  useLayoutEffect(() => {
    const el = field.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight + 2}px`;
  }, [editing, cell.source]);
  const toggle = editing ? "Pokaż tekst (Esc)" : "Edytuj Markdown";
  return (
    <div className="markdown-cell">
      <div className="gutter no-print">
        {/* mouse down would take the focus from the field (and show the text) before the click */}
        <button className="mode" onMouseDown={(e) => e.preventDefault()} onClick={() => setEditing(!editing)}
                title={toggle} aria-label={toggle} aria-pressed={editing}>
          {editing ? <Eye /> : <Pencil />}
        </button>
      </div>
      <div className="cell-body">
        {editing ? (
          <textarea
            ref={field}
            className="markdown-source no-print"
            autoFocus
            value={cell.source}
            spellCheck={false}
            placeholder="Tekst w Markdown: # nagłówek, **pogrubienie**, - lista, wzory w $…$"
            onChange={(e) => update({ source: e.target.value })}
            onBlur={() => setEditing(false)}
            onKeyDown={(e) => {
              if (e.key === "Escape" || (e.key === "Enter" && e.shiftKey)) {
                e.preventDefault();
                setEditing(false);
              }
            }}
          />
        ) : (
          <div className="markdown-view" onClick={(e) => (e.target as HTMLElement).closest("a") || setEditing(true)}
               title="Kliknij, żeby edytować">
            <Markdown source={cell.source || "*Pusty tekst — kliknij, żeby pisać.*"} />
          </div>
        )}
        {/* the PDF always shows the text, even when the cell is being edited */}
        {editing && <div className="markdown-view print-only"><Markdown source={cell.source} /></div>}
      </div>
    </div>
  );
}

/** Colab-style gutter: a round run button that shows [n] when the cell has run. */
function RunButton({ run, running, label, execution, done, icon = <Play /> }: {
  run: () => void; running: boolean; label: string; execution?: number;
  done?: boolean; // nothing changed since the last run: nothing to run
  icon?: ReactNode;
}) {
  return (
    <div className="gutter no-print">
      <button className={`run ${running ? "running" : ""} ${done ? "done" : ""}`} onClick={run} disabled={running || done}
              title={done ? "Wyniki są aktualne — zmień coś na schemacie, żeby przeliczyć" : label} aria-label={label}>
        {icon}
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
function ViewSwitch({ view, onSwitch, busy }: { view: SchematicView; onSwitch: (v: SchematicView) => void; busy: boolean }) {
  return (
    <div className="view-switch" role="tablist" aria-label="Widok komórki">
      <button role="tab" aria-selected={view === "schematic"} className={view === "schematic" ? "on" : ""}
              disabled={busy} onClick={() => onSwitch("schematic")} title="Schemat" aria-label="Schemat">
        <SchematicIcon />
      </button>
      <button role="tab" aria-selected={view === "code"} className={view === "code" ? "on" : ""}
              disabled={busy} onClick={() => onSwitch("code")} title="Kod — ten sam układ, do edycji" aria-label="Kod">
        <CodeIcon />
      </button>
    </div>
  );
}

/**
 * A schematic: while the cell is not being worked on, the drawing alone, as the PDF has it; once
 * it is (focused), the board to edit it — or its code.
 */
export function SchematicCell({ cell, update, library, simulate, running, focused }: {
  cell: Extract<Cell, { type: "schematic" }>;
  update: Update;
  library: SymbolLibrary;
  simulate: (schematic?: SchematicData) => void;
  running: boolean;
  focused: boolean;
}) {
  const empty = !cell.schematic.elements.length;
  const view: SchematicView = cell.view === "code" ? "code" : "schematic";
  // just clicked into: the board takes the keyboard at once (its shortcuts work without another click)
  const wasFocused = useRef(focused);
  const justFocused = focused && !wasFocused.current;
  wasFocused.current = focused;
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

  // leaving the cell with the code edited: the drawing takes it (the cell shows the drawing now)
  useEffect(() => {
    if (!focused && view === "code" && source !== null && source !== generated) void applied();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focused]);

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
  const problems = !cell.stale && cell.problems?.length ? <Problems problems={cell.problems} /> : null;

  return (
    <div className="schematic-cell">
      <RunButton run={run} running={running || busy} done={done || empty} icon={<Flash />}
                 label="Policz prądy i napięcia (Shift+Enter w kodzie)" />
      <div className="cell-body">
      {!focused ? (
        // not being worked on: the drawing as the document (the PDF) has it; a click edits it
        <div className="schematic-doc no-print" title="Kliknij, żeby edytować">
          {empty
            ? <p className="schematic-doc-empty">Pusty schemat — kliknij, żeby rysować.</p>
            : <PrintDrawing value={cell.schematic} library={library} onScreen />}
        </div>
      ) : view === "schematic" ? (
        <SchematicEditor
          value={cell.schematic}
          onChange={(schematic) => update({ schematic, ...(cell.results ? { stale: true } : {}) })}
          library={library}
          results={cell.stale ? undefined : cell.results}
          topLeft={name}
          topRight={actions}
          status={problems}
          camera={camera}
          autoFocus={focusBoard.current || justFocused}
        />
      ) : (
        <div className="board code-view">
          <div className="code-view-bar">
            <div className="island static name-island">{name}</div>
            <span className="spacer" />
            {problems && <div className="island static status">{problems}</div>}
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
          {error && <pre className="output-error code-view-note">{error}</pre>}
        </div>
      )}
      {/* the PDF shows the circuit as drawn; results belong to code cells: schematic(układ1, sol) */}
      <PrintDrawing value={cell.schematic} library={library} />
      {focused && cell.results && Object.keys(cell.results).length > 0 && (
        <ResultsTable results={cell.results} stale={!!cell.stale} />
      )}
      </div>
    </div>
  );
}

/** A warning / error sign on the board; a click unfolds what is wrong (with the names in LaTeX). */
function Problems({ problems }: { problems: Problem[] }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => { // a click anywhere else folds it again
    if (!open) return;
    const close = (event: PointerEvent) => { if (!ref.current?.contains(event.target as Node)) setOpen(false); };
    document.addEventListener("pointerdown", close);
    return () => document.removeEventListener("pointerdown", close);
  }, [open]);
  const error = problems.some((p) => p.kind === "error");
  const title = error ? "Błąd — nie da się policzyć" : "Nie wszystko da się wyznaczyć";
  return (
    <div className={`problems ${error ? "error" : "warning"}`} ref={ref}>
      <button className="icon problems-sign" onClick={() => setOpen((o) => !o)} title={title} aria-label={title}
              aria-expanded={open}>
        <WarningIcon />
      </button>
      {open && (
        <div className="problems-panel" role="dialog" aria-label={title}>
          <h4>{title}</h4>
          {problems.map((p, i) => <Markdown key={i} source={p.text} />)}
        </div>
      )}
    </div>
  );
}

/** "R_1" → R with a subscript 1. */
function Name({ id }: { id: string }) {
  const [base, ...sub] = id.split("_");
  return <>{base}{sub.length > 0 && <sub>{sub.join(",")}</sub>}</>;
}

/** What the run found, element by element. */
function ResultsTable({ results, stale }: { results: Record<string, ElementResult>; stale: boolean }) {
  return (
    <table className={`results no-print ${stale ? "stale" : ""}`}>
      <thead>
        <tr><th>Element</th><th>Wartość</th><th>Napięcie U</th><th>Prąd I</th><th>Moc P</th></tr>
      </thead>
      <tbody>
        {Object.entries(results).map(([id, r]) => (
          <tr key={id}>
            <td className="name"><Name id={id} /></td>
            <td className={r.solved ? "solved" : ""}>{r.value || "—"}</td>
            <td>{r.U ?? "—"}</td>
            <td>{r.I ?? "—"}</td>
            <td>{r.P ?? "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** "Układ 1" in the corner; a click edits it. In code the schematic is the variable układ1. */
function NameBox({ name, onRename }: { name: string; onRename: (name: string) => void }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(name);
  const commit = () => {
    setEditing(false);
    if (draft.trim()) onRename(draft.trim());
    else setDraft(name);
  };
  if (!editing)
    return (
      <button className="name-box" onClick={() => { setDraft(name); setEditing(true); }}
              title={`W kodzie: ${variableName(name)} — kliknij, żeby zmienić nazwę`}>
        {name}
      </button>
    );
  return (
    <span className="name-edit">
      <input autoFocus value={draft} spellCheck={false} aria-label="Nazwa schematu"
             onChange={(e) => setDraft(e.target.value)} onBlur={commit}
             onKeyDown={(e) => {
               if (e.key === "Enter") commit();
               if (e.key === "Escape") { setDraft(name); setEditing(false); }
             }} />
      <small>w kodzie: <code>{variableName(draft)}</code></small>
    </span>
  );
}

/** Mirrors kernel.variable(): "Układ 1" → układ1. */
export function variableName(name: string): string {
  const v = name.toLowerCase().replace(/[^\p{L}\p{N}_]/gu, "");
  if (!v) return "uklad";
  return /^\p{N}/u.test(v) ? `_${v}` : v;
}
