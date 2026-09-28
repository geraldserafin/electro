// Notes as cards (like Figma's files): a thumbnail of the first page, as the PDF would show it,
// and the title under it.
import type { NotePreview } from "@electro/notes-api";
import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { Link } from "react-router";
import { Markdown } from "@/shared/ui/Markdown";
import { More } from "@/shared/ui/icons";
import { PdfDrawing } from "@/features/schematic";
import type { SchematicData, SymbolLibrary } from "@/shared/model/types";

export const when = (iso: string) => {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const today = new Date().toDateString() === date.toDateString();
  return today
    ? `dziś, ${date.toLocaleTimeString("pl-PL", { hour: "2-digit", minute: "2-digit" })}`
    : date.toLocaleDateString("pl-PL", { day: "numeric", month: "long", year: "numeric" });
};

/** A card: a link to the note (or a button, for an example), with actions under "⋯". */
export function Card({ to, onClick, id, title, meta, preview, library, actions, index = 0 }: {
  index?: number; // its place in the list: the cards come in one after another
  to?: string;
  onClick?: () => void;
  id?: string;
  title: string;
  meta?: string;
  preview: NotePreview;
  library: SymbolLibrary;
  actions?: { label: string; danger?: boolean; run: () => void }[];
}) {
  const [menu, setMenu] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!menu) return;
    const close = (event: PointerEvent) => { if (!ref.current?.contains(event.target as Node)) setMenu(false); };
    document.addEventListener("pointerdown", close);
    return () => document.removeEventListener("pointerdown", close);
  }, [menu]);
  const body: ReactNode = (
    <>
      <span className="thumb"><PagePreview preview={preview} library={library} /></span>
      <span className="card-title">{title}</span>
      {meta && <span className="card-meta">{meta}</span>}
    </>
  );
  return (
    <div className="card appear" data-id={id} ref={ref} style={{ "--i": Math.min(index, 12) } as CSSProperties}>
      {to ? <Link className="card-open" to={to}>{body}</Link> : <button className="card-open" onClick={onClick}>{body}</button>}
      {actions && actions.length > 0 && (
        <>
          <button className="card-menu" onClick={() => setMenu(!menu)} title="Więcej" aria-label="Więcej" aria-expanded={menu}>
            <More />
          </button>
          {menu && (
            <div className="menu-items card-actions" role="menu">
              {actions.map((a) => (
                <button key={a.label} role="menuitem" className={a.danger ? "danger" : ""}
                        onClick={() => { setMenu(false); a.run(); }}>{a.label}</button>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

/** The first page, as in the PDF (always on white paper), drawn full size and scaled down. */
export function PagePreview({ preview, library }: { preview: NotePreview; library: SymbolLibrary }) {
  return (
    <div className="page" aria-hidden>
      {preview.cells.map((cell, i) =>
        cell.type === "markdown" ? <div key={i} className="markdown-view"><Markdown source={cell.source} /></div>
        : cell.type === "code" ? <pre key={i} className="page-code">{cell.source}</pre>
        : <PdfDrawing key={i} value={cell.schematic as unknown as SchematicData} library={library} />)}
    </div>
  );
}
