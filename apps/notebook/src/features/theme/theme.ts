// Light, dark, or as the system has it (and following it when it changes). data-theme on <html>
// is always "light" or "dark": tokens.css has the dark colours under [data-theme="dark"].
// Remembered in this browser; index.html sets it before the first paint, so no flash.
import { useState } from "react";

export const THEMES = ["system", "light", "dark"] as const;
export type Theme = (typeof THEMES)[number];

const KEY = "electro-theme";
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

/** The theme chosen, and choosing one (shown at once, remembered). */
export function useTheme(): [Theme, (theme: Theme) => void] {
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
  return [theme, choose];
}
