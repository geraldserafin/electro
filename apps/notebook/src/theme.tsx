// Light, dark, or as the system has it (and following it when it changes). data-theme on <html>
// is always "light" or "dark": styles.css has the dark colours under [data-theme="dark"].
// Remembered in this browser; index.html sets it before the first paint, so no flash.
import { useState } from "react";
import { Moon, Sun, System } from "./icons";

type Theme = "system" | "light" | "dark";

const KEY = "electro-theme";
const NEXT: Record<Theme, Theme> = { system: "light", light: "dark", dark: "system" };
const LABEL: Record<Theme, string> = { system: "systemowy", light: "jasny", dark: "ciemny" };
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
    <button className="float icon-button" onClick={() => choose(NEXT[theme])}
            title={`Motyw: ${LABEL[theme]} (kliknij: ${LABEL[NEXT[theme]]})`} aria-label={`Motyw: ${LABEL[theme]}`}>
      {ICON[theme]}
    </button>
  );
}
