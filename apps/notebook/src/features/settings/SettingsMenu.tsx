// The ⋯ island in the top right corner, like Excalidraw's menu: what the page gives it to do (a
// note: share it, export it); under a line the preferences — the theme, the language, and what the
// page adds (a note: its symbols); at the bottom who is signed in.
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Account } from "@/features/auth";
import { LanguageChoice } from "@/features/language";
import { ThemeChoice } from "@/features/theme";
import { MenuIsland, MenuSeparator } from "@/shared/ui/Menu";

export function SettingsMenu({ actions, preferences }: { actions?: ReactNode; preferences?: ReactNode }) {
  const { t } = useTranslation("settings");
  return (
    <MenuIsland label={t("label")}>
      {actions}
      {actions && <MenuSeparator />}
      <ThemeChoice />
      <LanguageChoice />
      {preferences}
      <Account />
    </MenuIsland>
  );
}
