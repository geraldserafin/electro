export const pl = {
  home: {
    brand: "electro — notatnik elektroniki",
    openFile: "Otwórz plik",
    openFileTitle: "Otwórz plik .electro.json jako nową notatkę",
    notes: "Notatki",
    examples: "Przykłady",
    fromExample: "nowa notatka z przykładu",
    deleteNote: "Usuń notatkę",
    confirmDelete: "Usunąć notatkę „{{title}}”? Tego nie da się cofnąć.",
    deleteFailed: "Nie udało się usunąć — serwer notatek nie odpowiada.",
    createFailed: "Serwer notatek nie odpowiada — spróbuj za chwilę.",
    listUnavailable: "Serwer notatek nie odpowiada — notatki pojawią się, gdy wróci.",
  },
  note: {
    missing: "Nie ma takiej notatki",
    maybeDeleted: "Może została usunięta.",
    unreachable: "Serwer notatek nie odpowiada",
    unreachableText: "Notatka jest na serwerze, a ten jest teraz niedostępny.",
    retry: "Spróbuj ponownie",
  },
  example: {
    missing: "Nie ma przykładu „{{name}}”.",
    unreachable: "Serwer notatek nie odpowiada.",
    creating: "Tworzę notatkę z przykładu…",
  },
};

export const en: typeof pl = {
  home: {
    brand: "electro — an electronics notebook",
    openFile: "Open a file",
    openFileTitle: "Open an .electro.json file as a new note",
    notes: "Notes",
    examples: "Examples",
    fromExample: "a new note from an example",
    deleteNote: "Delete note",
    confirmDelete: "Delete the note “{{title}}”? This cannot be undone.",
    deleteFailed: "Could not delete — the notes server is not responding.",
    createFailed: "The notes server is not responding — try again in a moment.",
    listUnavailable: "The notes server is not responding — the notes will show when it is back.",
  },
  note: {
    missing: "No such note",
    maybeDeleted: "Perhaps it was deleted.",
    unreachable: "The notes server is not responding",
    unreachableText: "The note is on the server, and the server is not available right now.",
    retry: "Try again",
  },
  example: {
    missing: "There is no example “{{name}}”.",
    unreachable: "The notes server is not responding.",
    creating: "Creating a note from the example…",
  },
};
