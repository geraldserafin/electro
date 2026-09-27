import { python } from "@codemirror/lang-python";
import CodeMirror from "@uiw/react-codemirror";
import { useState } from "react";
import { CodeIcon, Play } from "../icons";
import { SchematicEditor } from "../schematic/Editor";
import type { Cell, SymbolLibrary } from "../types";
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
          <CodeMirror
            value={cell.source}
            extensions={[python()]}
            basicSetup={{ foldGutter: false, highlightActiveLine: false }}
            onChange={(source) => update({ source })}
          />
        </div>
        <Outputs outputs={cell.outputs} />
      </div>
    </div>
  );
}

export function SchematicCell({ cell, update, library, showCode, simulate, running }: {
  cell: Extract<Cell, { type: "schematic" }>;
  update: Update;
  library: SymbolLibrary;
  showCode: () => void;
  simulate: () => void;
  running: boolean;
}) {
  const empty = !cell.schematic.elements.length;
  return (
    <div className="schematic-cell">
      <SchematicEditor
        value={cell.schematic}
        onChange={(schematic) => update({ schematic, ...(cell.results ? { stale: true } : {}) })}
        library={library}
        results={cell.stale ? undefined : cell.results}
        topLeft={
          <label className="schematic-name" title="Pod tą nazwą kod widzi schemat: schemat(&quot;…&quot;)">
            <code>schemat("</code>
            <input value={cell.name} onChange={(e) => update({ name: e.target.value })} spellCheck={false} />
            <code>")</code>
          </label>
        }
        topRight={
          <>
            <button className="ghost" onClick={showCode} disabled={empty} title="Wstaw pod spodem komórkę z kodem electro tego schematu">
              <CodeIcon /> Kod
            </button>
            <button className="primary" onClick={simulate} disabled={empty || running} title="Policz prądy i napięcia">
              <Play /> {running ? "Liczę…" : "Symuluj"}
            </button>
          </>
        }
      />
      <div className="sim-bar no-print">
        <label>
          Dane pomiarowe
          <input
            value={cell.data ?? ""}
            placeholder="dla niewiadomych, np. I_A_1 = 0; U_R_2 = 4"
            spellCheck={false}
            onChange={(e) => update({ data: e.target.value, ...(cell.results ? { stale: true } : {}) })}
            onKeyDown={(e) => e.key === "Enter" && simulate()}
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
