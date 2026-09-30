// Export to PDF: the note set by Typst (typst/) in the chosen theme, next to what can be set —
// what goes in (title and author, contents, code, outputs, values on drawings) and how (theme and
// its colour, paper, columns, header, page numbers, text). The pages shown are the file's own
// pages; the settings stay with the note.
import { useEffect } from "react";
import { createPortal } from "react-dom";
import { useTranslation } from "react-i18next";
import { cn } from "@/shared/lib/cn";
import type { Notebook } from "@/shared/model/types";
import { Close, CodeIcon, Export } from "@/shared/ui/icons";
import { Choice, Field, Group, Toggle } from "./controls";
import { Sheets } from "./Sheets";
import type { PdfSettings } from "./settings";
import { ThemeChoice } from "./ThemeChoice";
import { usePreview } from "./usePreview";

const action =
  "inline-flex flex-1 items-center justify-center gap-1.5 whitespace-nowrap px-3 py-2.25 rounded-[10px] border border-line " +
  "text-[15px] font-medium hover:enabled:bg-hover disabled:opacity-45";

export function ExportDialog({
  notebook,
  pdf,
  onChange,
  onCode,
  onClose,
}: {
  notebook: Notebook;
  pdf: PdfSettings;
  onChange: (patch: Partial<PdfSettings>) => void;
  onCode: (on: boolean) => void;
  onClose: () => void;
}) {
  const { t, i18n } = useTranslation("pdf-export");
  const { preview, busy } = usePreview(notebook, pdf, i18n.language);
  const codeInPdf = notebook.settings.codeInPdf;

  useEffect(() => {
    const esc = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [onClose]);

  // the PDF, or the Typst source it was set from (one .typ file)
  const download = (kind: "pdf" | "typ") => {
    if (preview.kind !== "ready") return;
    const blob =
      kind === "pdf"
        ? new Blob([preview.pdf as BlobPart], { type: "application/pdf" })
        : new Blob([preview.typst], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${fileName(notebook.title) || t("fileName")}.${kind}`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  const set =
    <K extends keyof PdfSettings>(key: K) =>
    (value: PdfSettings[K]) =>
      onChange({ [key]: value });
  const ready = preview.kind === "ready";
  return createPortal(
    <div
      className="fixed inset-0 z-100 grid place-items-center bg-[rgb(0_0_0/0.45)] animate-fade-in"
      data-keep-focus
      onPointerDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        role="dialog"
        aria-label={t("title")}
        className="appear relative grid grid-cols-[1fr_320px] max-[800px]:grid-cols-1 max-[800px]:grid-rows-[1fr_auto]
                      w-[min(1180px,94vw)] h-[min(860px,90vh)] rounded-[14px] overflow-hidden bg-surface border border-line"
      >
        <button
          onClick={onClose}
          title={t("closeHint")}
          aria-label={t("close")}
          className="absolute top-3 left-3 z-2 inline-flex size-9 items-center justify-center rounded-[10px] bg-surface shadow-island text-muted hover:text-fg"
        >
          <Close />
        </button>
        <Sheets preview={preview} busy={busy} />
        <aside className="flex flex-col gap-4.5 p-5 overflow-y-auto border-l border-line">
          <h2 className="m-0 text-[18px] font-semibold">{t("title")}</h2>
          <Group label={t("theme.label")}>
            <ThemeChoice pdf={pdf} onChange={onChange} />
          </Group>
          <Group label={t("heading.label")}>
            <Toggle label={t("heading.title")} on={pdf.title} set={set("title")} />
            <Field
              label={t("heading.author")}
              value={pdf.author}
              set={set("author")}
              placeholder={t("heading.authorPlaceholder")}
              disabled={!pdf.title}
            />
            <Toggle label={t("heading.date")} on={pdf.date} set={set("date")} disabled={!pdf.title} />
            <Toggle
              label={t("heading.titlePage")}
              hint={t("heading.titlePageHint")}
              on={pdf.titlePage}
              set={set("titlePage")}
              disabled={!pdf.title}
            />
          </Group>
          <Group label={t("content.label")}>
            <Toggle label={t("content.outline")} on={pdf.outline} set={set("outline")} />
            <Toggle
              label={t("content.numbering")}
              hint={t("content.numberingHint")}
              on={pdf.numbering}
              set={set("numbering")}
            />
            <Toggle label={t("content.sectionBreaks")} on={pdf.sectionBreaks} set={set("sectionBreaks")} />
            <Toggle label={t("content.code")} on={codeInPdf} set={onCode} />
            <Toggle label={t("content.codeLines")} on={pdf.codeLines} set={set("codeLines")} disabled={!codeInPdf} />
            <Toggle
              label={t("content.outputs")}
              hint={t("content.outputsHint")}
              on={pdf.outputs}
              set={set("outputs")}
            />
            <Toggle
              label={t("content.results")}
              hint={t("content.resultsHint")}
              on={pdf.results}
              set={set("results")}
            />
          </Group>
          <Group label={t("page.label")}>
            <Choice
              label={t("page.paper")}
              value={pdf.paper}
              set={set("paper")}
              options={[
                ["A4", "A4"],
                ["Letter", "Letter"],
              ]}
            />
            <Choice
              label={t("page.orientation")}
              value={pdf.orientation}
              set={set("orientation")}
              options={[
                ["portrait", t("page.portrait")],
                ["landscape", t("page.landscape")],
              ]}
            />
            <Choice
              label={t("page.margins")}
              value={pdf.margins}
              set={set("margins")}
              options={[
                ["narrow", t("page.narrow")],
                ["normal", t("page.normal")],
                ["wide", t("page.wide")],
              ]}
            />
            <Choice
              label={t("page.columns")}
              value={String(pdf.columns) as "1" | "2"}
              set={(c) => onChange({ columns: c === "2" ? 2 : 1 })}
              options={[
                ["1", t("page.one")],
                ["2", t("page.two")],
              ]}
            />
            <Toggle
              label={t("page.header")}
              hint={t("page.headerHint")}
              on={pdf.header}
              set={set("header")}
              disabled={!pdf.title}
            />
            <Toggle label={t("page.numbers")} on={pdf.pageNumbers} set={set("pageNumbers")} />
          </Group>
          <Group label={t("text.label")}>
            <Choice
              label={t("text.size")}
              value={pdf.text}
              set={set("text")}
              options={[
                ["small", t("text.small")],
                ["normal", t("text.normal")],
                ["large", t("text.large")],
              ]}
            />
            <Choice
              label={t("text.spacing")}
              value={pdf.spacing}
              set={set("spacing")}
              options={[
                ["tight", t("text.tight")],
                ["normal", t("text.normalSpacing")],
                ["loose", t("text.loose")],
              ]}
            />
            <Choice
              label={t("text.align")}
              value={pdf.align}
              set={set("align")}
              options={[
                ["theme", t("text.alignTheme")],
                ["left", t("text.left")],
                ["justify", t("text.justify")],
              ]}
            />
          </Group>
          {preview.kind === "ready" && preview.unreadable > 0 && (
            <p className="m-0 text-[12px] text-faint">{t("unreadable", { count: preview.unreadable })}</p>
          )}
          {/* the downloads: always in view at the bottom of the options, however far they are scrolled */}
          <div className="flex gap-2 mt-auto -mx-5 -mb-5 px-5 pt-3 pb-5 sticky -bottom-5 bg-surface border-t border-line">
            <button
              onClick={() => download("pdf")}
              disabled={!ready}
              className={cn(action, "bg-primary border-primary text-on-primary hover:enabled:bg-primary-hover")}
            >
              <Export /> {t("downloadPdf")}
            </button>
            <button onClick={() => download("typ")} disabled={!ready} title={t("typHint")} className={action}>
              <CodeIcon /> {t("downloadTyp")}
            </button>
          </div>
        </aside>
      </div>
    </div>,
    document.body,
  );
}

/** A file name from the title: without the characters file systems refuse (empty: none left). */
const fileName = (title: string) =>
  title
    .trim()
    .replace(/[\\/:*?"<>|]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
