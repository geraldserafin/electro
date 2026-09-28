import { useTranslation } from "react-i18next";
import { Moon, Sun, System } from "@/shared/ui/icons";
import { MenuGroup, MenuRadio } from "@/shared/ui/Menu";
import { THEMES, useTheme } from "./theme";

const ICON = { system: <System />, light: <Sun />, dark: <Moon /> };

/** The theme's group in a menu. */
export function ThemeChoice() {
  const { t } = useTranslation("theme");
  const [theme, choose] = useTheme();
  return (
    <MenuGroup label={t("label")}>
      {THEMES.map((it) => (
        <MenuRadio key={it} checked={theme === it} onSelect={() => choose(it)} icon={ICON[it]}>{t(it)}</MenuRadio>
      ))}
    </MenuGroup>
  );
}
