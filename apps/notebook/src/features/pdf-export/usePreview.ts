// The note set by Typst, again after every change: the PDF, its .typ source and its pages as
// images, for the dialog to show.
import { useEffect, useRef, useState } from "react";
import type { Notebook } from "@/shared/model/types";
import type { PdfSettings } from "./settings";
import { compile, warmUp } from "./typst/compile";
import { toTypst, typstFile } from "./typst/document";

export interface Page { url: string; width: number; height: number }

export type Preview =
  | { kind: "loading" }
  | { kind: "ready"; pdf: Uint8Array; pages: Page[]; unreadable: number; typst: string }
  | { kind: "failed"; error: string } // (empty: Typst said nothing)
  | { kind: "unshown" }; // set, but its pages would not load

/** The latest layout, and whether a newer one is on its way (busy: the one shown is going). */
export function usePreview(notebook: Notebook, pdf: PdfSettings, lang: string) {
  const [preview, setPreview] = useState<Preview>({ kind: "loading" });
  const [busy, setBusy] = useState(true);
  const codeInPdf = notebook.settings.codeInPdf;
  const settings = JSON.stringify(pdf); // (a new object every render: compared by what it says)
  const shown = useRef<Page[]>([]); // the pages' images, freed when replaced and when closing

  useEffect(warmUp, []);

  // a moment after the change: the drawings take the new settings first
  useEffect(() => {
    let alive = true;
    setBusy(true);
    const timer = window.setTimeout(async () => {
      const document = toTypst(notebook, pdf, drawingOf, lang);
      const out = await compile(document);
      if (!alive) return;
      setBusy(false);
      if (!out.ok) return setPreview({ kind: "failed", error: out.error });
      shown.current.forEach((p) => URL.revokeObjectURL(p.url));
      shown.current = pagesOf(out.svg);
      if (!shown.current.length) return setPreview({ kind: "unshown" });
      setPreview({ kind: "ready", pdf: out.pdf, pages: shown.current, unreadable: out.bad.length,
                   typst: typstFile(document, out.bad) });
    }, 150);
    return () => {
      alive = false;
      clearTimeout(timer);
    };
    // the note's content and the settings (compared by value)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [notebook.cells, notebook.title, codeInPdf, settings, lang]);

  useEffect(() => () => shown.current.forEach((p) => URL.revokeObjectURL(p.url)), []);

  return { preview, busy };
}

/** A schematic cell's drawing, as the page has it (the hidden drawing for the PDF). */
const drawingOf = (id: string) => document.querySelector<SVGSVGElement>(`#cell-${CSS.escape(id)} .pdf-drawing svg`);

/**
 * The pages of Typst's SVG (one tall picture: the pages one under another), each an image of its
 * own — its glyphs and styles with it, so nothing of it touches the app's own styles.
 */
function pagesOf(svg: string): Page[] {
  // (its script, for text selection in a live view, is not XML-safe — and not needed in an image)
  const doc = new DOMParser().parseFromString(svg.replace(/<script[\s\S]*?<\/script>/g, ""), "image/svg+xml");
  const root = doc.documentElement;
  const shared = Array.from(root.children).filter((el) => !el.classList.contains("typst-page"));
  const serializer = new XMLSerializer();
  const common = shared.map((el) => serializer.serializeToString(el)).join("");
  let y = 0;
  return Array.from(root.querySelectorAll(":scope > g.typst-page")).map((page) => {
    const width = Number(page.getAttribute("data-page-width"));
    const height = Number(page.getAttribute("data-page-height"));
    const top = Number(/translate\([^,]+,\s*([\d.]+)\)/.exec(page.getAttribute("transform") ?? "")?.[1] ?? y);
    y = top + height;
    const source = `<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 ${top} ${width} ${height}" width="${width}" height="${height}"><rect x="0" y="${top}" width="${width}" height="${height}" fill="#fff"/>${common}${serializer.serializeToString(page)}</svg>`;
    return { url: URL.createObjectURL(new Blob([source], { type: "image/svg+xml" })), width, height };
  });
}
