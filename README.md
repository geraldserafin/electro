# electro

Notatnik do elektroniki: obwody jako kod, solver z rozwiązaniem krok po kroku,
schematy, a docelowo notatnik webowy z eksportem sprawozdań do PDF.

| katalog | co to jest |
|---|---|
| [`packages/electro`](packages/electro) | biblioteka (Python): obwody jako morfizmy kategorii (`>>`, `\|`, `@`), zadania, solver z rozwiązaniem krok po kroku, prąd zmienny, symulacja w czasie, metody (Thévenin, superpozycja, upraszczanie, Bode, tolerancje), SPICE |
| [`packages/notes-api`](packages/notes-api) | kontrakt front ↔ backend notatek (TypeScript): schematy Effect Schema i `HttpApi` z błędami |
| [`apps/auth-worker`](apps/auth-worker) | Cloudflare Worker: połączenie z GitHubem (code → token) i proxy gita do GitHuba (którego git nie ma CORS) |
| [`apps/server`](apps/server) | dawny backend notatek (Effect, Postgres) — na razie nieużywany: notatki są w przeglądarce |
| [`apps/notebook`](apps/notebook) | notatnik w przeglądarce (React + Pyodide): Markdown, kod, edytor schematów na siatce, symulacja na żywo, eksport PDF |

Python liczy, strona pokazuje: `electro` to model i matematyka, a rysunek, układanie schematu, symbole,
wykresy i plik notatki są w TypeScripcie. Między nimi płyną tylko dane (netlista, wyniki, kroki, serie liczb).

```python
from electro import *

E, R_1, R_2, A = VoltageSource("E"), Resistor("R_1"), Resistor("R_2"), Node("A")
uklad = Problem(GND >> E >> R_1 >> A >> R_2 >> GND, {E: 12, R_1: 10, I(R_1): 1}, [Parameter(R_2)])
sol = solve(uklad)
sol(Parameter(R_2))   # 2
sol.steps             # kroki, każdy z równaniem i jego powodem
```

## Notatki: w przeglądarce, kopia na GitHubie

```
apps/notebook ──HttpApiClient──▶ /api (w stronie: features/vault/api.ts) ──▶ repo git w IndexedDB (isomorphic-git)
      │  (@effect-atom: lista, zapis,                                           │ Zapisz / ⌘S: commit,
      │   otwieranie, usuwanie)                                                 ▼ a z GitHubem: fetch, scalenie, push
      └──────── packages/notes-api: jeden kontrakt ─────────       github.com/<user>/electro-notes (prywatne)
                                                                    przez apps/auth-worker (/git/…)
```

- **Serwera nie ma.** Notatnik jest statyczną stroną (GitHub Pages, `.github/workflows/pages.yml`). Kontrakt
  `packages/notes-api` został: klient woła `/api` jak dawniej, tylko odpowiada mu kod w stronie, nad vaultem.
- **Vault to repo git w przeglądarce.** `library.json` (foldery i to, co w którym leży), `notes/<id>.json`
  (dokumenty; nazwa notatki to jej tytuł) i `firmware/<sha-256>`. Zmiany trafiają do plików na bieżąco,
  a **Zapisz** (⌘S / Ctrl+S) robi commit. Kropka na przycisku znaczy, że coś nie jest zapisane.
- **GitHub jest opcjonalny.** „Połącz z GitHubem” pod przyciskiem zapisu (OAuth, zakres `repo`) zakłada prywatne
  `electro-notes`. Od tej pory Zapisz też synchronizuje: pobiera commity z GitHuba, scala je plik po pliku
  (`merge.ts`) i wypycha. Notatkę zmienioną w obu miejscach zostawia w wersji z przeglądarki, a wersję
  z GitHuba dokłada obok jako kopię. Nic nie ginie.
- **Worker robi to, czego strona nie może.** Wymienia kod z GitHuba na token (to wymaga sekretu aplikacji)
  i przekazuje ruch gita do github.com, bo git GitHuba nie odpowiada stronom (brak CORS).

`devenv up` stawia notatnik (:5190), workera (:8787, `wrangler dev`) i przebudowę paczki Pythona.
Konfiguracja połączenia z GitHubem jest opisana w `.env.example`.

## Dlaczego takie formaty

- **SVG** działa bez zmian w przeglądarce, w Jupyterze i w PDF-ie.
- **Markdown + LaTeX (`$...$`)** czyta Jupyter, web (markdown-it + KaTeX) i generatory PDF
  (Typst przez `cmarker`/`mitex` albo pandoc).
- Obiekty `Svg` i `Markdown` mają `_repr_svg_` / `_repr_markdown_`, więc same się wyświetlają w notatnikach.

## Praca w repo

```sh
devenv up                          # notatnik na http://localhost:5190 (+ przebudowa Pythona przy zmianach)
devenv shell                       # python + sympy + pytest, node + pnpm (pnpm install robi się sam)
pytest                             # testy paczek Pythona i kernela notatnika
```

To jest workspace `uv` (`[tool.uv.workspace]` w `pyproject.toml`), więc działa też `uv sync && uv run pytest`.
