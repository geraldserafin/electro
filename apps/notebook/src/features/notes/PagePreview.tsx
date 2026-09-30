import type { NotePreview } from "@electro/notes-api";
import { PdfDrawing } from "@/features/schematic";
import type { SchematicData, SymbolLibrary } from "@/shared/model/types";
import { Markdown } from "@/shared/ui/Markdown";
import "./PagePreview.css";

/** The first page, as in the PDF (always on white paper), drawn full size and scaled down (to a
 *  card, or ``width`` px: a small one in a folder's picture). */
export function PagePreview({
  preview,
  library,
  width,
}: {
  preview: NotePreview;
  library: SymbolLibrary;
  width?: number;
}) {
  return (
    <div className="page" aria-hidden style={width ? { transform: `scale(${width / 794})` } : undefined}>
      {preview.cells.map((cell, i) =>
        cell.type === "markdown" ? (
          <div key={i} className="markdown-view">
            <Markdown source={cell.source} links={false} />
          </div>
        ) : cell.type === "code" ? (
          <pre key={i} className="page-code">
            {cell.source}
          </pre>
        ) : (
          <PdfDrawing key={i} value={cell.schematic as unknown as SchematicData} library={library} />
        ),
      )}
    </div>
  );
}
