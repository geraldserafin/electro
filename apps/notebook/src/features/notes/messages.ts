export const pl = {
  untitled: "Bez tytułu",
  today: "dziś, {{time}}",
  more: "Więcej",
  newNote: "Nowa notatka",
  sync: {
    conflict: "Ta notatka zmieniła się gdzie indziej. Którą wersję zostawić?",
    keepMine: "Moją",
    takeTheirs: "Z serwera",
    offline: "Serwer notatek nie odpowiada — zmiany wyślę, gdy wróci.",
    failed: "Nie udało się zapisać ({{tag}}).",
    mismatch: "Nie udało się zapisać: adres wskazuje inną notatkę niż dokument.",
  },
  readOnly: {
    text: "Tylko do odczytu — zmiany tutaj się nie zapiszą.",
    copy: "Zrób kopię",
    copyTitle: "{{title}} (kopia)",
    copyFailed: "Nie udało się zrobić kopii — serwer notatek nie odpowiada.",
  },
};

export const en: typeof pl = {
  untitled: "Untitled",
  today: "today, {{time}}",
  more: "More",
  newNote: "New note",
  sync: {
    conflict: "This note has changed somewhere else. Which version should stay?",
    keepMine: "Mine",
    takeTheirs: "The server's",
    offline: "The notes server is not responding — changes will be sent when it is back.",
    failed: "Could not save ({{tag}}).",
    mismatch: "Could not save: the address names a different note than the document.",
  },
  readOnly: {
    text: "Read only — changes here are not saved.",
    copy: "Make a copy",
    copyTitle: "{{title}} (copy)",
    copyFailed: "Could not make a copy — the notes server is not responding.",
  },
};
