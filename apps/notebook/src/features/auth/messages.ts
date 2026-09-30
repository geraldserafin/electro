export const pl = {
  account: "GitHub",
  connect: "Połącz z GitHubem",
  connected: "Notatki zapisują się też na GitHubie (electro-notes)",
  disconnect: "Rozłącz GitHuba",
  confirmDisconnect: "Rozłączyć GitHuba? Najpierw zapiszę na nim wszystkie zmiany.",
  notSaved:
    "Nie udało się zapisać zmian na GitHubie. Rozłączyć mimo to? Zmiany, których tam nie ma, zostaną w tej przeglądarce.",
  wipe: "Usunąć też notatki z tej przeglądarki? Są bezpieczne na GitHubie. (Anuluj: zostaną tutaj.)",
  otherAccount:
    "Notatki w tej przeglądarce były zapisywane na koncie {{from}}. Dołączyć je do notatek konta {{to}}? (Anuluj: najpierw usunę je z tej przeglądarki — na GitHubie {{from}} zostaną.)",
  notConfigured:
    "Połączenie z GitHubem nie jest skonfigurowane: brakuje VITE_GITHUB_CLIENT_ID (aplikacji OAuth na GitHubie, zob. .env.example).",
};

export const en: typeof pl = {
  account: "GitHub",
  connect: "Connect GitHub",
  connected: "Notes are saved on GitHub too (electro-notes)",
  disconnect: "Disconnect GitHub",
  confirmDisconnect: "Disconnect GitHub? Every change is saved there first.",
  notSaved: "The changes could not be saved on GitHub. Disconnect anyway? Changes not there stay in this browser.",
  wipe: "Delete the notes from this browser too? They are safe on GitHub. (Cancel: they stay here.)",
  otherAccount:
    "The notes in this browser were saved to {{from}}'s account. Join them with {{to}}'s notes? (Cancel: they are deleted from this browser first — on GitHub, {{from}}'s stay.)",
  notConfigured:
    "Connecting GitHub is not set up: VITE_GITHUB_CLIENT_ID (a GitHub OAuth app, see .env.example) is missing.",
};
