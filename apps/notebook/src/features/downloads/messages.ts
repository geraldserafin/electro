export const pl = {
  label: "Pobieranie",
  title: "Pobieranie narzędzi",
  hint: "Pobiera się tylko raz — potem przeglądarka trzyma to u siebie.",
  groups: {
    python: "Python i biblioteka electro",
    compiler: "Kompilator szkiców (clang)",
    uno: "Biblioteki Arduino Uno",
    pico: "Biblioteki Raspberry Pi Pico",
    pdf: "Skład PDF (Typst i czcionki)",
  },
  of: "{{loaded}} z {{total}}",
  done: "gotowe",
  failed: "nie udało się — spróbuje ponownie",
  files_one: "{{count}} plik",
  files_few: "{{count}} pliki",
  files_many: "{{count}} plików",
  files_other: "{{count}} pliku",
};

export const en: typeof pl = {
  label: "Downloads",
  title: "Downloading the tools",
  hint: "Downloaded once — then the browser keeps it.",
  groups: {
    python: "Python and the electro library",
    compiler: "The sketch compiler (clang)",
    uno: "Arduino Uno libraries",
    pico: "Raspberry Pi Pico libraries",
    pdf: "PDF typesetting (Typst and fonts)",
  },
  of: "{{loaded}} of {{total}}",
  done: "done",
  failed: "failed — it will try again",
  files_one: "{{count}} file",
  files_few: "{{count}} files",
  files_many: "{{count}} files",
  files_other: "{{count}} files",
};
