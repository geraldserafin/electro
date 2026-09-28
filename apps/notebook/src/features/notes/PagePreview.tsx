import type { NotePreview } from "@electro/notes-api";
import { PdfDrawing } from "@/features/schematic";
import type { SchematicData, SymbolLibrary } from "@/shared/model/types";
import { Markdown } from "@/shared/ui/Markdown";
import "./PagePreview.css";

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
