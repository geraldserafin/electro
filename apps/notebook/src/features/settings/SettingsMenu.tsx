// The ⋯ island in the top right corner: who is signed in, and how the app looks and speaks (the
// theme, the language).
import { useTranslation } from "react-i18next";
import { Account } from "@/features/auth";
import { LanguageChoice } from "@/features/language";
import { ThemeChoice } from "@/features/theme";
import { MenuIsland } from "@/shared/ui/Menu";

export function SettingsMenu() {
  const { t } = useTranslation("settings");
  return (
    <MenuIsland label={t("label")}>
      <Account />
      <ThemeChoice />
      <LanguageChoice />
    </MenuIsland>
  );
}
