// Export to PDF: the note set by Typst (typst/) in the chosen theme, next to what can be set —
// what goes in (title and author, contents, code, outputs, values on drawings) and how (theme and
// its colour, paper, columns, header, page numbers, text). The pages shown are the file's own
// pages; the settings stay with the note.
import { useEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { Close, CodeIcon, Export } from "../icons";
import type { Notebook } from "../types";
import type { PdfSettings, Theme } from "./settings";
import { compile, warmUp } from "./typst/compile";
import { toTypst, typstFile } from "./typst/document";

const THEMES: [Theme, string, string][] = [
  ["classic", "Klasyczny", "jak LaTeX"],
  ["modern", "Nowoczesny", "bezszeryfowy, żółty akcent"],
  ["elegant", "Elegancki", "jak książka"],
];

// the accent colours to choose from (besides the theme's own, shown first)
const ACCENTS = ["#1f4e99", "#0f766e", "#2f7d32", "#b3261e", "#6d28d9", "#c2410c"];
const THEME_ACCENT: Record<Theme, string> = { classic: "#1f1f1f", modern: "#f5b100", elegant: "#7a1f3d" }; // as in electro.typ

type State =
  | { kind: "loading" }
  | { kind: "ready"; pdf: Uint8Array; pages: Page[]; unreadable: number; typst: string }
  | { kind: "failed"; error: string };

interface Page { url: string; width: number; height: number }

export function ExportDialog({ notebook, pdf, onChange, onCode, onClose }: {
  notebook: Notebook;
  pdf: PdfSettings;
  onChange: (patch: Partial<PdfSettings>) => void;
  onCode: (on: boolean) => void;
  onClose: () => void;
}) {
  const [state, setState] = useState<State>({ kind: "loading" });
  const [busy, setBusy] = useState(true);
  const codeInPdf = notebook.settings.codeInPdf;
  const settings = JSON.stringify(pdf); // (a new object every render: compared by what it says)
  const shown = useRef<Page[]>([]); // the pages' images, freed when replaced and when closing

  useEffect(() => {
    const esc = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [onClose]);

  useEffect(warmUp, []);

  // the document again after every change (a moment later: the drawings take the new settings first)
  useEffect(() => {
    let alive = true;
    setBusy(true);
    const timer = window.setTimeout(async () => {
      const document = toTypst(notebook, pdf, drawingOf);
      const out = await compile(document);
      if (!alive) return;
      setBusy(false);
      if (!out.ok) return setState({ kind: "failed", error: out.error });
      shown.current.forEach((p) => URL.revokeObjectURL(p.url));
      shown.current = pagesOf(out.svg);
      if (!shown.current.length) return setState({ kind: "failed", error: "podgląd stron się nie wczytał" });
      setState({ kind: "ready", pdf: out.pdf, pages: shown.current, unreadable: out.bad.length,
                typst: typstFile(document, out.bad) });
    }, 150);
    return () => {
      alive = false;
      clearTimeout(timer);
    };
    // the note's content and the settings (compared by value)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [notebook.cells, notebook.title, codeInPdf, settings]);

  useEffect(() => () => shown.current.forEach((p) => URL.revokeObjectURL(p.url)), []);

  // the PDF, or the Typst source it was set from (one .typ file)
  const download = (kind: "pdf" | "typ") => {
    if (state.kind !== "ready") return;
    const blob = kind === "pdf"
      ? new Blob([state.pdf as BlobPart], { type: "application/pdf" })
      : new Blob([state.typst], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${fileName(notebook.title)}.${kind}`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  const pages = state.kind === "ready" ? state.pages.length : 0;
  return createPortal(
    <div className="export-backdrop" onPointerDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="export-dialog" role="dialog" aria-label="Eksport do PDF">
        <button className="export-close icon-button" onClick={onClose} title="Zamknij (Esc)" aria-label="Zamknij"><Close /></button>
        <div className={`export-preview ${busy ? "busy" : ""}`}>
          {state.kind === "loading" && <p className="export-wait">Przygotowuję skład PDF…</p>}
          {state.kind === "failed" && <p className="export-wait error">Nie udało się złożyć PDF: {state.error}</p>}
          {state.kind === "ready" && (
            <div className="export-sheets">
              {state.pages.map((page, i) => (
                <img key={page.url} className="sheet" src={page.url} alt={`Strona ${i + 1}`}
                     style={{ aspectRatio: `${page.width} / ${page.height}` }} />
              ))}
            </div>
          )}
          {pages > 0 && <span className="export-pages">{pages} {plural(pages, "strona", "strony", "stron")}</span>}
        </div>
        <aside className="export-options">
          <h2>Eksport do PDF</h2>
          <Group label="Motyw">
            <div className="theme-choice" role="radiogroup" aria-label="Motyw">
              {THEMES.map(([theme, name, hint]) => (
                <button key={theme} role="radio" aria-checked={pdf.theme === theme} className={`theme-${theme} ${pdf.theme === theme ? "on" : ""}`}
                        onClick={() => onChange({ theme })}>
                  <span className="theme-sample">Aa</span>
                  <span className="theme-name">{name}</span>
                  <small>{hint}</small>
                </button>
              ))}
            </div>
            <div className="export-choice">
              <span>Kolor akcentu</span>
              <div className="swatches" role="radiogroup" aria-label="Kolor akcentu">
                {[null, ...ACCENTS].map((color) => (
                  <button key={color ?? "theme"} role="radio" aria-checked={pdf.accent === color} className={pdf.accent === color ? "on" : ""}
                          title={color ? color : "Jak w motywie"} aria-label={color ?? "Jak w motywie"}
                          style={{ background: color ?? THEME_ACCENT[pdf.theme] }} onClick={() => onChange({ accent: color })} />
                ))}
              </div>
            </div>
          </Group>
          <Group label="Tytuł">
            <Toggle label="Tytuł" on={pdf.title} set={(title) => onChange({ title })} />
            <label className={`export-field ${pdf.title ? "" : "disabled"}`}>
              <span>Autor</span>
              <input value={pdf.author} placeholder="pod tytułem" disabled={!pdf.title} spellCheck={false}
                     onChange={(e) => onChange({ author: e.target.value })} />
            </label>
            <Toggle label="Data pod tytułem" on={pdf.date} set={(date) => onChange({ date })} disabled={!pdf.title} />
            <Toggle label="Strona tytułowa" hint="tytuł sam na pierwszej stronie" on={pdf.titlePage}
                    set={(titlePage) => onChange({ titlePage })} disabled={!pdf.title} />
          </Group>
          <Group label="W dokumencie">
            <Toggle label="Spis treści" on={pdf.outline} set={(outline) => onChange({ outline })} />
            <Toggle label="Numerowane nagłówki" hint="1., 1.1., …" on={pdf.numbering} set={(numbering) => onChange({ numbering })} />
            <Toggle label="Rozdziały od nowej strony" on={pdf.sectionBreaks} set={(sectionBreaks) => onChange({ sectionBreaks })} />
            <Toggle label="Kod komórek" on={codeInPdf} set={onCode} />
            <Toggle label="Numery wierszy kodu" on={pdf.codeLines} set={(codeLines) => onChange({ codeLines })} disabled={!codeInPdf} />
            <Toggle label="Wyniki kodu" hint="to, co komórki wypisały i narysowały" on={pdf.outputs} set={(outputs) => onChange({ outputs })} />
            <Toggle label="Wartości na schematach" hint="prądy i napięcia z ostatniego uruchomienia" on={pdf.results}
                    set={(results) => onChange({ results })} />
          </Group>
          <Group label="Strona">
            <Choice label="Papier" value={pdf.paper} set={(paper) => onChange({ paper })}
                    options={[["A4", "A4"], ["Letter", "Letter"]]} />
            <Choice label="Orientacja" value={pdf.orientation} set={(orientation) => onChange({ orientation })}
                    options={[["portrait", "Pionowo"], ["landscape", "Poziomo"]]} />
            <Choice label="Marginesy" value={pdf.margins} set={(margins) => onChange({ margins })}
                    options={[["narrow", "Wąskie"], ["normal", "Zwykłe"], ["wide", "Szerokie"]]} />
            <Choice label="Kolumny" value={String(pdf.columns) as "1" | "2"} set={(c) => onChange({ columns: c === "2" ? 2 : 1 })}
                    options={[["1", "Jedna"], ["2", "Dwie"]]} />
            <Toggle label="Tytuł w nagłówku" hint="na każdej stronie poza pierwszą" on={pdf.header}
                    set={(header) => onChange({ header })} disabled={!pdf.title} />
            <Toggle label="Numery stron" on={pdf.pageNumbers} set={(pageNumbers) => onChange({ pageNumbers })} />
          </Group>
          <Group label="Tekst">
            <Choice label="Rozmiar" value={pdf.text} set={(text) => onChange({ text })}
                    options={[["small", "Mały"], ["normal", "Zwykły"], ["large", "Duży"]]} />
            <Choice label="Odstępy między wierszami" value={pdf.spacing} set={(spacing) => onChange({ spacing })}
                    options={[["tight", "Ciasne"], ["normal", "Zwykłe"], ["loose", "Luźne"]]} />
            <Choice label="Wyrównanie" value={pdf.align} set={(align) => onChange({ align })}
                    options={[["theme", "Jak motyw"], ["left", "Do lewej"], ["justify", "Obustronne"]]} />
          </Group>
          {state.kind === "ready" && state.unreadable > 0 && (
            <p className="export-note">
              Nie każdy wzór dało się złożyć ({state.unreadable}): Typst nie zna któregoś z poleceń LaTeX, więc w PDF jest sam zapis.
            </p>
          )}
          <div className="export-actions">
            <button className="primary" onClick={() => download("pdf")} disabled={state.kind !== "ready"}><Export /> Pobierz PDF</button>
            <button onClick={() => download("typ")} disabled={state.kind !== "ready"} title="Źródło w Typst: jeden plik .typ">
              <CodeIcon /> Pobierz .typ
            </button>
          </div>
        </aside>
      </div>
    </div>,
    document.body,
  );
}

/** A schematic cell's drawing, as the page has it (the hidden drawing for the PDF). */
const drawingOf = (id: string) => document.querySelector<SVGSVGElement>(`#cell-${CSS.escape(id)} .pdf-drawing svg`);

/** Polish plurals: 1 strona, 2–4 (22–24, …) strony, 5+ (and 12–14) stron. */
const plural = (n: number, one: string, few: string, many: string) =>
  n === 1 ? one : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 12 || n % 100 > 14) ? few : many;

/** A file name from the title: without the characters file systems refuse. */
const fileName = (title: string) => title.trim().replace(/[\\/:*?"<>|]+/g, " ").replace(/\s+/g, " ").trim() || "notatka";

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

function Group({ label, children }: { label: string; children: ReactNode }) {
  return <section className="export-group"><h3>{label}</h3>{children}</section>;
}

function Toggle({ label, hint, on, set, disabled }: {
  label: string; hint?: string; on: boolean; set: (on: boolean) => void; disabled?: boolean;
}) {
  return (
    <label className={`export-toggle ${disabled ? "disabled" : ""}`}>
      <span><span>{label}</span>{hint && <small>{hint}</small>}</span>
      <input type="checkbox" role="switch" checked={on} disabled={disabled} onChange={(e) => set(e.target.checked)} />
    </label>
  );
}

function Choice<T extends string>({ label, value, set, options }: {
  label: string; value: T; set: (v: T) => void; options: [T, string][];
}) {
  return (
    <div className="export-choice">
      <span>{label}</span>
      <div className="segmented" role="radiogroup" aria-label={label}>
        {options.map(([v, text]) => (
          <button key={v} role="radio" aria-checked={value === v} className={value === v ? "on" : ""} onClick={() => set(v)}>
            {text}
          </button>
        ))}
      </div>
    </div>
  );
}
