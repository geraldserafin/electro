// What goes into the PDF and how it is set: kept with the note (settings.pdf), so the export looks
// the same every time. The PDF is set by Typst (typst/): these choose its theme and its parts.
import { createContext, useContext } from "react";

export type Theme = "classic" | "modern" | "elegant";

export interface PdfSettings {
  theme: Theme;
  accent: string | null; // a colour for headings, links, rules (#rrggbb); none: the theme's
  title: boolean; // the title at the top
  author: string; // under the title (empty: none)
  date: boolean; // today's date under it
  titlePage: boolean; // the title (and the contents) on a page of their own
  outline: boolean; // a table of contents after the title
  numbering: boolean; // headings numbered: 1., 1.1., …
  sectionBreaks: boolean; // each top section from a new page
  outputs: boolean; // what code cells printed / drew
  codeLines: boolean; // line numbers beside the code
  results: boolean; // values found by a run, on the drawings
  paper: "A4" | "Letter";
  orientation: "portrait" | "landscape";
  margins: "narrow" | "normal" | "wide";
  columns: 1 | 2;
  text: "small" | "normal" | "large";
  spacing: "tight" | "normal" | "loose"; // between lines
  align: "theme" | "left" | "justify";
  header: boolean; // the title at the top of every page but the first
  pageNumbers: boolean;
}

export const DEFAULTS: PdfSettings = {
  theme: "classic",
  accent: null,
  title: true,
  author: "",
  date: false,
  titlePage: false,
  outline: false,
  numbering: false,
  sectionBreaks: false,
  outputs: true,
  codeLines: false,
  results: false,
  paper: "A4",
  orientation: "portrait",
  margins: "normal",
  columns: 1,
  text: "normal",
  spacing: "normal",
  align: "theme",
  header: false,
  pageNumbers: false,
};

/** The note's settings, completed with the defaults (older notes have none). */
export const pdfOf = (settings: Record<string, unknown>): PdfSettings => ({
  ...DEFAULTS,
  ...(settings.pdf as Partial<PdfSettings>),
});

/** The note's PDF settings, for what draws for it (the hidden drawings). */
export const PdfContext = createContext<PdfSettings>(DEFAULTS);
export const usePdf = () => useContext(PdfContext);
