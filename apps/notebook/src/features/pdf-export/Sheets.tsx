// The pages, as Typst set them (images), one under another; a new layout fades in over the old.
import { useTranslation } from "react-i18next";
import { cn } from "@/shared/lib/cn";
import type { Preview } from "./usePreview";

const message = "m-0 absolute inset-0 grid place-items-center p-8 text-center";

export function Sheets({ preview, busy }: { preview: Preview; busy: boolean }) {
  const { t } = useTranslation("pdf-export");
  const pages = preview.kind === "ready" ? preview.pages : [];
  return (
    <div className="group/preview relative min-h-0 bg-hover" data-preview data-busy={busy || undefined}>
      {preview.kind === "loading" && <p className={cn(message, "text-muted")}>{t("preparing")}</p>}
      {preview.kind === "failed" && (
        <p className={cn(message, "text-danger")}>
          {preview.error ? t("failed", { error: preview.error }) : t("failedPlain")}
        </p>
      )}
      {preview.kind === "unshown" && <p className={cn(message, "text-danger")}>{t("noPreview")}</p>}
      {pages.length > 0 && (
        <>
          <div className="h-full overflow-y-auto pt-6 px-8 pb-16 grid justify-items-center content-start gap-5">
            {pages.map((page, i) => (
              <img
                key={page.url}
                src={page.url}
                alt={t("sheet", { n: i + 1 })}
                data-sheet
                style={{ aspectRatio: `${page.width} / ${page.height}` }}
                className="w-[min(100%,640px)] h-auto bg-white rounded-[2px] transition-opacity duration-200 group-data-busy/preview:opacity-60
                              shadow-[0_1px_3px_rgb(0_0_0/0.16),0_6px_20px_rgb(0_0_0/0.1)]"
              />
            ))}
          </div>
          <span className="absolute left-1/2 bottom-3 -translate-x-1/2 px-3 py-1 rounded-full text-[13px] bg-surface border border-line text-muted">
            {t("pages", { count: pages.length })}
          </span>
        </>
      )}
    </div>
  );
}
