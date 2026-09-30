// The ⋯ island in the top right corner, like Excalidraw's menu: what the page gives it to do (a
// note: export it); under a line the preferences — the theme, the language, and what the page adds
// (a note: its symbols). Before it, the save button (GitHub is connected there, too).
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { LanguageChoice } from "@/features/language";
import { SaveButton } from "@/features/notes";
import { ThemeChoice } from "@/features/theme";
import { MenuIsland, MenuSeparator } from "@/shared/ui/Menu";

export function SettingsMenu({ actions, preferences }: { actions?: ReactNode; preferences?: ReactNode }) {
  const { t } = useTranslation("settings");
  return (
    <>
      <SaveButton />
      <MenuIsland label={t("label")}>
        {actions}
        {actions && <MenuSeparator />}
        <ThemeChoice />
        <LanguageChoice />
        {preferences}
      </MenuIsland>
    </>
  );
}
