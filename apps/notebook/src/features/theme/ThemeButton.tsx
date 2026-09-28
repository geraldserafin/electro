// Light, dark, or as the system has it (and following it when it changes). data-theme on <html>
// is always "light" or "dark": styles.css has the dark colours under [data-theme="dark"].
// Remembered in this browser; index.html sets it before the first paint, so no flash.
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Moon, Sun, System } from "@/shared/ui/icons";
import { IslandButton } from "@/shared/ui/Island";

type Theme = "system" | "light" | "dark";

const KEY = "electro-theme";
const NEXT: Record<Theme, Theme> = { system: "light", light: "dark", dark: "system" };
const ICON = { system: <System />, light: <Sun />, dark: <Moon /> };
const systemDark = matchMedia("(prefers-color-scheme: dark)");

function saved(): Theme {
  try {
    const theme = localStorage.getItem(KEY);
    if (theme === "light" || theme === "dark") return theme;
  } catch {
    // no storage: the system's
  }
  return "system";
}

function apply(theme: Theme) {
  document.documentElement.dataset.theme = theme === "system" ? (systemDark.matches ? "dark" : "light") : theme;
}

systemDark.addEventListener("change", () => apply(saved()));

export function ThemeButton() {
  const { t } = useTranslation("theme");
  const [theme, setTheme] = useState(saved);
  const choose = (next: Theme) => {
    setTheme(next);
    apply(next);
    try {
      if (next === "system") localStorage.removeItem(KEY);
      else localStorage.setItem(KEY, next);
    } catch {
      // not remembered — fine
    }
  };
  return (
    <IslandButton onClick={() => choose(NEXT[theme])}
            title={t("next", { name: t(theme), next: t(NEXT[theme]) })} aria-label={t("theme", { name: t(theme) })}>
      {ICON[theme]}
    </IslandButton>
  );
}
