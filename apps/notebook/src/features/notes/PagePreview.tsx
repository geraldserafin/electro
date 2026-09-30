import type { NotePreview } from "@electro/notes-api";
import { useLayoutEffect, useRef, useState } from "react";
import { PdfDrawing } from "@/features/schematic";
import type { SchematicData, SymbolLibrary } from "@/shared/model/types";
import { Markdown } from "@/shared/ui/Markdown";
import "./PagePreview.css";

const PAGE = 794; // px: A4 at 96 dpi, as the PDF has it

/** The first page, as in the PDF (always on white paper), drawn full size and scaled down to the
 *  box it is in (a card, as wide as the grid's column; a small one in a folder's picture). */
export function PagePreview({ preview, library }: { preview: NotePreview; library: SymbolLibrary }) {
  const page = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState<number | null>(null);
  useLayoutEffect(() => {
    const box = page.current?.parentElement;
    if (!box) return;
    const measure = () => setScale(box.clientWidth / PAGE);
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(box);
    return () => observer.disconnect();
  }, []);
  return (
    <div
      ref={page}
      className="page"
      aria-hidden
      style={scale === null ? { visibility: "hidden" } : { transform: `scale(${scale})` }}
    >
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
