import { python } from "@codemirror/lang-python";
import CodeMirror from "@uiw/react-codemirror";
import { useState } from "react";
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
        <Markdown source={cell.source || "*(pusty tekst — dwuklik, żeby pisać)*"} />
      </div>
    );
  return (
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
  );
}

export function CodeCell({ cell, update, run, running }: {
  cell: Extract<Cell, { type: "code" }>; update: Update; run: () => void; running: boolean;
}) {
  return (
    <div className={`code-cell ${running ? "running" : ""}`}>
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
        <button className="run no-print" onClick={run} disabled={running} title="Uruchom (Shift+Enter)">
          {running ? "…" : "▶"}
        </button>
        <CodeMirror
          value={cell.source}
          extensions={[python()]}
          basicSetup={{ foldGutter: false, highlightActiveLine: false }}
          onChange={(source) => update({ source })}
        />
      </div>
      <Outputs outputs={cell.outputs} />
    </div>
  );
}

export function SchematicCell({ cell, update, library, showCode }: {
  cell: Extract<Cell, { type: "schematic" }>; update: Update; library: SymbolLibrary | null; showCode: () => void;
}) {
  return (
    <div className="schematic-cell">
      <div className="schematic-name no-print">
        Schemat <code>schemat("</code>
        <input value={cell.name} onChange={(e) => update({ name: e.target.value })} />
        <code>")</code>
        <span className="spacer" />
        <button onClick={showCode} disabled={!library || !cell.schematic.elements.length}
                title="Wstaw pod spodem komórkę z kodem electro tego schematu">
          Pokaż kod
        </button>
      </div>
      {library
        ? <SchematicEditor value={cell.schematic} onChange={(schematic) => update({ schematic })} library={library} />
        : <p className="muted">Ładowanie symboli…</p>}
    </div>
  );
}
