// All notes as a gallery (like Figma's files): a thumbnail of each note's first page, as the PDF
// would show it, with its title under it. The first card starts a new note.
import { Result, useAtomValue } from "@effect-atom/atom-react";
import type { NotePreview, NoteSummary } from "@electro/notes-api";
import { useEffect, useRef, useState } from "react";
import { Markdown } from "../cells/Markdown";
import { More, Plus } from "../icons";
import { PrintDrawing } from "../schematic/Editor";
import type { SchematicData, SymbolLibrary } from "../types";
import { notesAtom } from "./atoms";

export const when = (iso: string) => {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const today = new Date().toDateString() === date.toDateString();
  return today
    ? `dziś, ${date.toLocaleTimeString("pl-PL", { hour: "2-digit", minute: "2-digit" })}`
    : date.toLocaleDateString("pl-PL", { day: "numeric", month: "long", year: "numeric" });
};

export function Gallery({ currentId, library, onOpen, onCreate, onDelete }: {
  currentId: string;
  library: SymbolLibrary;
  onOpen: (id: string) => void;
  onCreate: () => void;
  onDelete: (note: NoteSummary) => void;
}) {
  const notes = useAtomValue(notesAtom);
  return (
    <div className="gallery">
      <h1>Notatki</h1>
      <div className="gallery-grid">
        <button className="card new" onClick={onCreate}>
          <span className="thumb"><Plus /></span>
          <span className="card-title">Nowa notatka</span>
        </button>
        {Result.builder(notes)
          .onInitial(() => null)
          .onFailure(() => null)
          .onSuccess((list) => list.map((note) => (
            <Card key={note.id} note={note} current={note.id === currentId} library={library}
                  onOpen={() => onOpen(note.id)} onDelete={() => onDelete(note)} />
          )))
          .render()}
      </div>
      {Result.isFailure(notes) && (
        <p className="gallery-note">Serwer notatek jest niedostępny — otwarty notatnik zapisuje się w tej przeglądarce.</p>
      )}
    </div>
  );
}

function Card({ note, current, library, onOpen, onDelete }: {
  note: NoteSummary; current: boolean; library: SymbolLibrary; onOpen: () => void; onDelete: () => void;
}) {
  const [menu, setMenu] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!menu) return;
    const close = (event: PointerEvent) => { if (!ref.current?.contains(event.target as Node)) setMenu(false); };
    document.addEventListener("pointerdown", close);
    return () => document.removeEventListener("pointerdown", close);
  }, [menu]);
  return (
    <div className={`card ${current ? "current" : ""}`} data-id={note.id} ref={ref}>
      <button className="card-open" onClick={onOpen} aria-current={current}>
        <span className="thumb"><PagePreview preview={note.preview} library={library} /></span>
        <span className="card-title">{note.title || "Bez tytułu"}</span>
        <span className="card-meta">{current ? "otwarta · " : ""}{when(note.modified)}</span>
      </button>
      <button className="card-menu" onClick={() => setMenu(!menu)} title="Więcej" aria-label="Więcej" aria-expanded={menu}>
        <More />
      </button>
      {menu && (
        <div className="menu-items card-actions" role="menu">
          <button role="menuitem" className="danger" onClick={() => { setMenu(false); onDelete(); }}>Usuń notatkę</button>
        </div>
      )}
    </div>
  );
}

/** The first page, as in the PDF (always on white paper), drawn full size and scaled down. */
function PagePreview({ preview, library }: { preview: NotePreview; library: SymbolLibrary }) {
  return (
    <div className="page" aria-hidden>
      {preview.cells.map((cell, i) =>
        cell.type === "markdown" ? <div key={i} className="markdown-view"><Markdown source={cell.source} /></div>
        : cell.type === "code" ? <pre key={i} className="page-code">{cell.source}</pre>
        : <PrintDrawing key={i} value={cell.schematic as unknown as SchematicData} library={library} />)}
    </div>
  );
}
