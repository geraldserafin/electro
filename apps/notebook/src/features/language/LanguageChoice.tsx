import { useTranslation } from "react-i18next";
import { MenuGroup, MenuRadio } from "@/shared/ui/Menu";
import { chooseLanguage, LANGUAGES } from "./language";

/** The language's group in a menu: each language by its own name (Polski, English). */
export function LanguageChoice() {
  const { t, i18n } = useTranslation("language");
  return (
    <MenuGroup label={t("label")}>
      {LANGUAGES.map((lng) => (
        <MenuRadio key={lng} checked={i18n.language === lng} onSelect={() => chooseLanguage(lng)}>
          <span lang={lng}>{t(`name.${lng}` as const)}</span>
        </MenuRadio>
      ))}
    </MenuGroup>
  );
}
