// What goes into the PDF and how it is set: kept with the note (settings.pdf), so the export —
// and plain Ctrl+P — look the same every time.
import { createContext, useContext } from "react";

export interface PdfSettings {
  title: boolean; // the title at the top
  date: boolean; // today's date under it
  outputs: boolean; // what code cells printed / drew
  results: boolean; // values found by a run, on the drawings
  paper: "A4" | "Letter";
  orientation: "portrait" | "landscape";
  margins: "narrow" | "normal" | "wide";
  text: "small" | "normal" | "large";
  pageNumbers: boolean;
}

export const DEFAULTS: PdfSettings = {
  title: true, date: false, outputs: true, results: false,
  paper: "A4", orientation: "portrait", margins: "normal", text: "normal", pageNumbers: false,
};

/** The note's settings, completed with the defaults (older notes have none). */
export const pdfOf = (settings: Record<string, unknown>): PdfSettings => ({ ...DEFAULTS, ...(settings.pdf as Partial<PdfSettings>) });

const MARGINS = { narrow: [12, 12], normal: [18, 16], wide: [25, 22] } as const; // mm: top/bottom, left/right
const TEXT = { small: "10pt", normal: "11pt", large: "12.5pt" } as const;
const PAPER = { A4: [210, 297], Letter: [215.9, 279.4] } as const; // mm, portrait

/** The paper's size and the room for content on it, in mm. */
export function geometry(pdf: PdfSettings) {
  const [w, h] = PAPER[pdf.paper];
  const [width, height] = pdf.orientation === "portrait" ? [w, h] : [h, w];
  const [my, mx] = MARGINS[pdf.margins];
  return { width, height, marginX: mx, marginY: my, contentWidth: width - 2 * mx, contentHeight: height - 2 * my };
}

/** The print style for these settings: the page, the text size, page numbers. */
export function pageCss(pdf: PdfSettings): string {
  const g = geometry(pdf);
  const numbers = pdf.pageNumbers
    ? `@bottom-center { content: counter(page) " / " counter(pages); font: 9pt system-ui, sans-serif; color: #666; }`
    : "";
  return `@media print {
  @page { size: ${pdf.paper} ${pdf.orientation}; margin: ${g.marginY}mm ${g.marginX}mm; ${numbers} }
  ${textCss(pdf)}
}`;
}

/** The text size on paper. */
export const textCss = (pdf: PdfSettings) => `.notebook { font-size: ${TEXT[pdf.text]}; }`;

/** Classes on the notebook that switch parts of the print on and off. */
export const printClasses = (pdf: PdfSettings, codeInPdf: boolean) =>
  [codeInPdf ? "" : "hide-code-in-print", pdf.title ? "" : "pdf-no-title", pdf.outputs ? "" : "pdf-no-outputs"]
    .filter(Boolean).join(" ");

/** For the drawings: show the values a run found (settings.pdf.results). */
export const PdfContext = createContext<PdfSettings>(DEFAULTS);
export const usePdf = () => useContext(PdfContext);
