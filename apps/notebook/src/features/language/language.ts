// The app's language: the one chosen, remembered in this browser; until then the browser's own
// (the first of its languages the app speaks), English when it speaks none of them.
import i18n from "i18next";

export const LANGUAGES = ["pl", "en"] as const;
export type Language = (typeof LANGUAGES)[number];

const KEY = "electro-language";

export function savedLanguage(): Language {
  try {
    const saved = localStorage.getItem(KEY);
    if (LANGUAGES.includes(saved as Language)) return saved as Language;
  } catch {
    // no storage: the browser's
  }
  return browserLanguage();
}

function browserLanguage(): Language {
  for (const tag of navigator.languages ?? [navigator.language]) {
    const language = tag.slice(0, 2).toLowerCase() as Language;
    if (LANGUAGES.includes(language)) return language;
  }
  return "en";
}

export function chooseLanguage(language: Language) {
  void i18n.changeLanguage(language);
  try {
    localStorage.setItem(KEY, language);
  } catch {
    // not remembered — fine
  }
}
