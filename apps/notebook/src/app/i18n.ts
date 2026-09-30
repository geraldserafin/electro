// The app's languages. Each slice keeps its own messages (messages.ts: pl, and en of the same
// shape) as one namespace; here they come together. Keys are checked by TypeScript: t("…") takes
// only keys the Polish messages have.
import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import { messages as auth } from "@/features/auth";
import { messages as language, savedLanguage } from "@/features/language";
import { messages as library } from "@/features/library";
import { messages as notebook } from "@/features/notebook";
import { messages as notes } from "@/features/notes";
import { messages as pdfExport } from "@/features/pdf-export";
import { messages as schematic } from "@/features/schematic";
import { messages as settings } from "@/features/settings";
import { messages as sharing } from "@/features/sharing";
import { messages as simulation } from "@/features/simulation";
import { messages as solution } from "@/features/solution";
import { messages as theme } from "@/features/theme";
import * as pages from "@/pages/messages";

const resources = {
  pl: {
    notebook: notebook.pl,
    notes: notes.pl,
    schematic: schematic.pl,
    simulation: simulation.pl,
    library: library.pl,
    sharing: sharing.pl,
    solution: solution.pl,
    "pdf-export": pdfExport.pl,
    theme: theme.pl,
    settings: settings.pl,
    language: language.pl,
    auth: auth.pl,
    pages: pages.pl,
  },
  en: {
    notebook: notebook.en,
    notes: notes.en,
    schematic: schematic.en,
    simulation: simulation.en,
    library: library.en,
    sharing: sharing.en,
    solution: solution.en,
    "pdf-export": pdfExport.en,
    theme: theme.en,
    settings: settings.en,
    language: language.en,
    auth: auth.en,
    pages: pages.en,
  },
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
i18n.on("languageChanged", (lng) => {
  document.documentElement.lang = lng;
});
