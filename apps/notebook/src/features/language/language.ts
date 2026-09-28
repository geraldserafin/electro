// The app's language: the one chosen, remembered in this browser; Polish until then.
// (Later, once every slice speaks English too: the browser's language before a choice.)
import i18n from "i18next";

export const LANGUAGES = ["pl", "en"] as const;
export type Language = (typeof LANGUAGES)[number];

const KEY = "electro-language";

export function savedLanguage(): Language {
  try {
    const saved = localStorage.getItem(KEY);
    if (LANGUAGES.includes(saved as Language)) return saved as Language;
  } catch {
    // no storage: the default
  }
  return "pl";
}

export function chooseLanguage(language: Language) {
  void i18n.changeLanguage(language);
  try {
    localStorage.setItem(KEY, language);
  } catch {
    // not remembered — fine
  }
}
