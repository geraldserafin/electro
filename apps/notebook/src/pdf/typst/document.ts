// A note as a Typst document: main.typ (the cells, in order), config.typ (the settings and the
// formulas) and the drawings as SVG files. electro.typ (the theme) gives the pieces their look.
import type { Notebook, Output } from "../../types";
import type { PdfSettings } from "../settings";
import { markdownToTypst, str, text, topHeading } from "./markdown";

export interface TypstDocument {
  main: string;
  /** config.typ, with `__BAD__` where the formulas mitex cannot read go (filled in when compiling). */
  config: string;
  files: Record<string, string>; // path → SVG
}

const PAPER = { A4: "a4", Letter: "us-letter" } as const;
const MARGINS = { narrow: "(x: 14mm, y: 14mm)", normal: "(x: 20mm, y: 22mm)", wide: "(x: 28mm, y: 28mm)" } as const;
const SIZE = { small: "10pt", normal: "11pt", large: "12pt" } as const;
const PX = 0.75; // an SVG's px in pt

/**
 * ``drawingOf``: a schematic cell's drawing as SVG, as the page has it (the hidden print drawing —
 * with the values of the last run, when the settings want them); none when it is empty.
 */
export function toTypst(notebook: Notebook, pdf: PdfSettings, drawingOf: (cellId: string) => SVGSVGElement | null): TypstDocument {
  const formulas: string[] = [];
  const files: Record<string, string> = {};
  const math = (latex: string, block: boolean) => {
    formulas.push(latex.trim());
    return `#${block ? "M" : "m"}(${formulas.length - 1})`;
  };
  // the note's top heading level is the document's first (a note may start its sections at ##)
  const tops = notebook.cells.flatMap((c) => (c.type === "markdown" ? [topHeading(c.source)] : [])).filter((d) => d !== null);
  const shift = tops.length ? Math.min(...tops) - 1 : 0;
  const md = (source: string) => markdownToTypst(source, math, shift);
  const image = (svg: SVGSVGElement, halo: boolean) => {
    const path = `d${Object.keys(files).length}.svg`;
    const { source, width } = forTypst(svg, halo);
    files[path] = source;
    return `#drawing(${str(path)}, ${(width * PX).toFixed(1)}pt)`;
  };
  const output = (o: Output): string => {
    switch (o.type) {
      case "markdown": return md(o.data);
      case "error": return `#error(${str(o.data.trimEnd())})`;
      case "warning": return `#warning[${text(o.data)}]`;
      case "svg": {
        const svg = parseSvg(o.data);
        return svg ? image(svg, false) : "";
      }
      default: return o.data.trim() ? `#output(${str(o.data.trimEnd())})` : "";
    }
  };

  const parts: string[] = [];
  for (const cell of notebook.cells) {
    if (cell.type === "markdown") parts.push(md(cell.source));
    else if (cell.type === "code") {
      if (notebook.settings.codeInPdf && cell.source.trim()) parts.push(`#code(${str(cell.source.trimEnd())})`);
      if (pdf.outputs) parts.push(...cell.outputs.map(output));
    } else {
      const svg = drawingOf(cell.id);
      if (svg) parts.push(image(svg, true));
    }
  }

  const date = new Date().toLocaleDateString("pl-PL", { day: "numeric", month: "long", year: "numeric" });
  const config = `#let config = (
  theme: ${str(pdf.theme)},
  title: ${pdf.title && notebook.title.trim() ? str(notebook.title.trim()) : "none"},
  date: ${pdf.title && pdf.date ? str(date) : "none"},
  paper: ${str(PAPER[pdf.paper])},
  flipped: ${pdf.orientation === "landscape"},
  margin: ${MARGINS[pdf.margins]},
  size: ${SIZE[pdf.text]},
  page-numbers: ${pdf.pageNumbers},
  numbering: ${pdf.numbering},
  outline: ${pdf.outline},
)
#let formulas = (${formulas.map((f) => `${str(f)},`).join(" ")})
#let bad = (__BAD__)
`;
  const main = `#import "electro.typ": *
#show: note

${parts.filter((p) => p.trim()).join("\n\n")}
`;
  return { main, config, files };
}

function parseSvg(source: string): SVGSVGElement | null {
  const doc = new DOMParser().parseFromString(source, "image/svg+xml");
  const root = doc.documentElement;
  return root.nodeName === "svg" && !doc.querySelector("parsererror") ? (root as unknown as SVGSVGElement) : null;
}

/**
 * An SVG as Typst can draw it: black ink on white paper (no CSS variables, no page styles), text in
 * the generic sans (Typst's SVG renderer finds fonts that way), and — for a drawing from the board —
 * the white halo its labels have on the page.
 */
function forTypst(svg: SVGSVGElement, halo: boolean): { source: string; width: number } {
  const copy = svg.cloneNode(true) as SVGSVGElement;
  copy.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  copy.setAttribute("color", "#000");
  copy.removeAttribute("class");
  // what the board needs and its page styles hide (areas to click): Typst would fill them black
  copy.querySelectorAll(".hit, .pin-handle, .open-pin, .snap, .ghost, .draft, .rubber-band").forEach((el) => el.remove());
  copy.querySelectorAll("style").forEach((style) => {
    style.textContent = (style.textContent ?? "")
      .replace(/var\(--[\w-]+\s*,\s*([^)]+)\)/g, "$1")
      .replace(/var\(--[\w-]+\)/g, "#000")
      .replace(/font:\s*([\d.]+px)[^;}]*/g, "font-size:$1;font-family:sans-serif");
  });
  const extra = document.createElementNS("http://www.w3.org/2000/svg", "style");
  extra.textContent = "text{font-family:sans-serif}"
    + (halo
      ? ".solved{fill:#000}text{paint-order:stroke;stroke:#fff;stroke-width:4px;stroke-linejoin:round}"
        + ".letter{stroke:none}.label{font-size:13px}.label .sub{font-size:10px}.reading{font-size:11px;fill:#2f9e44}"
      : "");
  copy.appendChild(extra);
  const width = Number.parseFloat(copy.getAttribute("width") ?? "") || copy.viewBox.baseVal?.width || 400;
  return { source: new XMLSerializer().serializeToString(copy), width };
}
