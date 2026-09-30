import { useTranslation } from "react-i18next";
import { MenuRow, MenuSelect } from "@/shared/ui/Menu";
import { chooseLanguage, LANGUAGES, type Language } from "./language";

/** The language, a row of the settings menu: a drop-down, each language by its own name (Polski, English). */
export function LanguageChoice() {
  const { t, i18n } = useTranslation("language");
  return (
    <MenuRow label={t("label")}>
      <MenuSelect
        label={t("label")}
        value={i18n.language as Language}
        onChange={chooseLanguage}
        options={LANGUAGES.map((lng) => ({ value: lng, label: t(`name.${lng}` as const) }))}
      />
    </MenuRow>
  );
}
