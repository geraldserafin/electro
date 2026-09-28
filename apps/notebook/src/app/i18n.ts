// The app's languages. Each slice keeps its own messages (messages.ts: pl, and en of the same
// shape) as one namespace; here they come together. Keys are checked by TypeScript: t("…") takes
// only keys the Polish messages have.
import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import { messages as language, savedLanguage } from "@/features/language";
import { messages as notes } from "@/features/notes";
import { messages as theme } from "@/features/theme";
import * as home from "@/pages/Home.messages";

const resources = {
  pl: { notes: notes.pl, theme: theme.pl, language: language.pl, home: home.pl },
  en: { notes: notes.en, theme: theme.en, language: language.en, home: home.en },
};

declare module "i18next" {
  interface CustomTypeOptions {
    resources: (typeof resources)["pl"];
  }
}

void i18n.use(initReactI18next).init({
  resources,
  lng: savedLanguage(),
  fallbackLng: "pl",
  interpolation: { escapeValue: false }, // React escapes
  initAsync: false, // the messages are here already: ready before the first render
});

document.documentElement.lang = i18n.language;
i18n.on("languageChanged", (lng) => { document.documentElement.lang = lng; });
