// The PDF's theme, each shown by a sample of its type, and its accent colour.
import { useTranslation } from "react-i18next";
import { Labelled } from "./controls";
import type { PdfSettings, Theme } from "./settings";

const THEMES = ["classic", "modern", "elegant"] as const satisfies Theme[];

// the sample's type: as the theme sets text (electro.typ)
const SAMPLE: Record<Theme, string> = {
  classic: "font-['Latin_Modern_Roman','Computer_Modern',Georgia,serif]",
  modern: "font-['Inter',var(--sans)] font-semibold after:block after:w-4 after:h-0.75 after:bg-primary",
  elegant: "font-['Libertinus_Serif','Palatino_Linotype',Palatino,serif] [font-variant:small-caps]",
};

// the accent colours to choose from (besides the theme's own, shown first)
const ACCENTS = ["#1f4e99", "#0f766e", "#2f7d32", "#b3261e", "#6d28d9", "#c2410c"];
const THEME_ACCENT: Record<Theme, string> = { classic: "#1f1f1f", modern: "#f5b100", elegant: "#7a1f3d" }; // as in electro.typ

export function ThemeChoice({ pdf, onChange }: { pdf: PdfSettings; onChange: (patch: Partial<PdfSettings>) => void }) {
  const { t } = useTranslation("pdf-export", { keyPrefix: "theme" });
  return (
    <>
      <div className="grid grid-cols-[repeat(3,1fr)] gap-1.5" role="radiogroup" aria-label={t("label")}>
        {THEMES.map((theme) => (
          <button
            key={theme}
            role="radio"
            aria-checked={pdf.theme === theme}
            onClick={() => onChange({ theme })}
            className="grid items-center justify-items-start gap-0 px-2.5 py-2 rounded-[10px] border border-line text-left text-[15px]
                             not-aria-checked:hover:bg-hover aria-checked:border-fg aria-checked:bg-selected"
          >
            <span className={`text-[22px] leading-[1.2] ${SAMPLE[theme]}`}>Aa</span>
            <span className="text-[13px] font-medium">{t(theme)}</span>
            <small className="text-[11px] leading-[1.3] text-muted">{t(`${theme}Hint`)}</small>
          </button>
        ))}
      </div>
      <Labelled label={t("accent")}>
        <div className="flex flex-wrap gap-2" role="radiogroup" aria-label={t("accent")}>
          {[null, ...ACCENTS].map((color) => (
            <button
              key={color ?? "theme"}
              role="radio"
              aria-checked={pdf.accent === color}
              title={color ?? t("accentTheme")}
              aria-label={color ?? t("accentTheme")}
              style={{ background: color ?? THEME_ACCENT[pdf.theme] }}
              onClick={() => onChange({ accent: color })}
              className="size-6 rounded-full border-2 border-surface shadow-[0_0_0_1px_var(--line)] aria-checked:shadow-[0_0_0_2px_var(--text)]"
            />
          ))}
        </div>
      </Labelled>
    </>
  );
}
