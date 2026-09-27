// Export to PDF: the pages as they will print, next to what can be set — what goes in (code,
// outputs, title, date, values on drawings) and how (paper, orientation, margins, text, page
// numbers). The settings stay with the note; printing is the browser's ("Save as PDF").
import { useEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { Export } from "../icons";
import { geometry, textCss, type PdfSettings } from "./settings";

const MM = 96 / 25.4; // CSS px per mm

export function ExportDialog({ pdf, codeInPdf, title, onChange, onCode, onClose }: {
  pdf: PdfSettings;
  codeInPdf: boolean;
  title: string;
  onChange: (patch: Partial<PdfSettings>) => void;
  onCode: (on: boolean) => void;
  onClose: () => void;
}) {
  useEffect(() => {
    const esc = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [onClose]);

  const print = () => {
    const before = document.title;
    document.title = title || "notatka"; // the browser offers it as the PDF's file name
    window.addEventListener("afterprint", () => (document.title = before), { once: true });
    window.print();
  };

  return createPortal(
    <div className="export-backdrop no-print" onPointerDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="export-dialog" role="dialog" aria-label="Eksport do PDF">
        <Preview pdf={pdf} codeInPdf={codeInPdf} />
        <aside className="export-options">
          <h2>Eksport do PDF</h2>
          <Group label="W dokumencie">
            <Toggle label="Tytuł" on={pdf.title} set={(title) => onChange({ title })} />
            <Toggle label="Data pod tytułem" on={pdf.date} set={(date) => onChange({ date })} disabled={!pdf.title} />
            <Toggle label="Kod komórek" on={codeInPdf} set={onCode} />
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
            <Choice label="Tekst" value={pdf.text} set={(text) => onChange({ text })}
                    options={[["small", "Mały"], ["normal", "Zwykły"], ["large", "Duży"]]} />
            <Toggle label="Numery stron" hint="Chrome i Edge" on={pdf.pageNumbers} set={(pageNumbers) => onChange({ pageNumbers })} />
          </Group>
          <div className="export-actions">
            <button onClick={onClose}>Zamknij</button>
            <button className="primary" onClick={print}><Export /> Drukuj / zapisz PDF</button>
          </div>
          <p className="export-note">Podgląd dzieli strony w przybliżeniu — ostateczne podziały ustala przeglądarka.</p>
        </aside>
      </div>
    </div>,
    document.body,
  );
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

// ------------------------------------------------------------------ the preview

/** The app's styles as the printer sees them: print rules always on, the dark theme off, no @page. */
function printStyles(): string {
  const out: string[] = [];
  const walk = (rules: CSSRuleList) => {
    for (const rule of Array.from(rules)) {
      if (rule instanceof CSSMediaRule) {
        const media = rule.media.mediaText;
        if (media.includes("print")) walk(rule.cssRules);
        else if (!media.includes("prefers-color-scheme")) out.push(rule.cssText);
      } else if (!(rule instanceof CSSPageRule)) out.push(rule.cssText);
    }
  };
  for (const sheet of Array.from(document.styleSheets)) {
    try {
      walk(sheet.cssRules);
    } catch {
      // a sheet from elsewhere (fonts): not needed for the layout
    }
  }
  return out.join("\n");
}

/** The notebook as it prints: a copy of the page without what is never printed. */
function printedNotebook(): string {
  const source = document.querySelector(".notebook");
  if (!source) return "";
  const copy = source.cloneNode(true) as HTMLElement;
  copy.querySelectorAll(".no-print, .cell-tools, .add-row, .island").forEach((el) => el.remove());
  return copy.outerHTML;
}

function Preview({ pdf, codeInPdf }: { pdf: PdfSettings; codeInPdf: boolean }) {
  const frame = useRef<HTMLIFrameElement>(null);
  const [pages, setPages] = useState(0);

  useEffect(() => {
    // after the notebook took the new settings (its classes, the date line) — then lay out pages
    const timer = window.setTimeout(() => {
      const doc = frame.current?.contentDocument;
      if (!doc || !frame.current) return;
      const g = geometry(pdf);
      const content = printedNotebook();
      doc.open();
      doc.write(`<!doctype html><html><head><style>${printStyles()}</style><style>${textCss(pdf)}</style><style>
        html { background: transparent; } body { margin: 0; padding: 16px; background: transparent; }
        .measure { width: ${g.contentWidth}mm; position: absolute; visibility: hidden; }
        .sheet { position: relative; width: ${g.width}mm; height: ${g.height}mm; margin: 0 auto 16px; background: #fff;
                 box-shadow: 0 1px 3px rgba(0,0,0,.18), 0 6px 20px rgba(0,0,0,.12); overflow: hidden; }
        .sheet-inner { position: absolute; left: ${g.marginX}mm; top: ${g.marginY}mm; width: ${g.contentWidth}mm;
                       height: ${g.contentHeight}mm; overflow: hidden; }
        .page-number { position: absolute; bottom: ${g.marginY / 2}mm; left: 0; right: 0; text-align: center;
                       font: 9pt system-ui, sans-serif; color: #666; }
      </style></head><body><div class="measure">${content}</div></body></html>`);
      doc.close();
      const layout = () => {
        const measure = doc.querySelector<HTMLElement>(".measure");
        if (!measure || !frame.current) return;
        const pageHeight = g.contentHeight * MM;
        const count = Math.max(1, Math.ceil(measure.scrollHeight / pageHeight));
        measure.remove();
        doc.body.innerHTML = Array.from({ length: count }, (_, i) => `
          <div class="sheet"><div class="sheet-inner"><div style="margin-top: ${-i * pageHeight}px">${content}</div></div>
          ${pdf.pageNumbers ? `<div class="page-number">${i + 1} / ${count}</div>` : ""}</div>`).join("");
        const fit = Math.min(1, (frame.current.clientWidth - 32) / (g.width * MM));
        doc.documentElement.style.zoom = String(fit);
        setPages(count);
      };
      // KaTeX fonts and the like: lay out once they are in
      void (doc.fonts?.ready ?? Promise.resolve()).then(layout);
    }, 120);
    return () => clearTimeout(timer);
  }, [pdf, codeInPdf]);

  return (
    <div className="export-preview">
      <iframe ref={frame} title="Podgląd PDF" />
      {pages > 0 && <span className="export-pages">{pages} {pages === 1 ? "strona" : pages < 5 ? "strony" : "stron"}</span>}
    </div>
  );
}
