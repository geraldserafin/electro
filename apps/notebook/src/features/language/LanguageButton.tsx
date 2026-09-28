import { useTranslation } from "react-i18next";
import { IslandButton } from "@/shared/ui/Island";
import { chooseLanguage, LANGUAGES, type Language } from "./language";

/** An island with the language's code; a click: the next one. */
export function LanguageButton() {
  const { t, i18n } = useTranslation("language");
  const current = i18n.language as Language;
  const next = LANGUAGES[(LANGUAGES.indexOf(current) + 1) % LANGUAGES.length];
  return (
    <IslandButton onClick={() => chooseLanguage(next)}
            title={t("switch", { lng: next })} aria-label={t("switch", { lng: next })}>
      <span className="text-[13px] font-medium tracking-wide uppercase">{current}</span>
    </IslandButton>
  );
}
