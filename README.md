# electro

Notatnik do elektroniki: obwody jako kod, solver z rozwiązaniem krok po kroku,
schematy, a docelowo notatnik webowy z eksportem sprawozdań do PDF.

| katalog | co to jest |
|---|---|
| [`packages/electro`](packages/electro) | rdzeń: obwody jako morfizmy kategorii, kombinatory `+`/`\|`, solver, `find`, `Hole` |
| [`packages/electro-schematic`](packages/electro-schematic) | rysunek na siatce: model (JSON), rysunek → obwód, auto-layout kodu, edycja (`move`, `rotate`) |
| [`packages/electro-render`](packages/electro-render) | wygląd: biblioteka symboli (też jako JSON dla edytora), schemat → SVG, ślad rozwiązania → Markdown + LaTeX |
| [`packages/notes-api`](packages/notes-api) | kontrakt front ↔ backend notatek (TypeScript): schematy Effect Schema i `HttpApi` z błędami |
| [`apps/auth-worker`](apps/auth-worker) | Cloudflare Worker: połączenie z GitHubem (code → token) i proxy gita do GitHuba (którego git nie ma CORS) |
| [`apps/server`](apps/server) | dawny backend notatek (Effect, Postgres) — na razie nieużywany: notatki są w przeglądarce |
| [`apps/notebook`](apps/notebook) | notatnik w przeglądarce (React + Pyodide): Markdown, kod, edytor schematów na siatce, eksport PDF |

```
electro  ◀──  electro-schematic  ◀──  electro-render  ◀──  apps/notebook (Pyodide + edytor w TS)
solver        gdzie co leży            jak to wygląda
```

```python
from electro import *
from electro_render import schematic, steps

uklad = supply(12) + Resistor(10) + node("A") + shunt(Resistor()) + Resistor(5) + ground
sol = uklad.solve(I_R_1=1, find="R_2")

schematic(uklad, sol).save("uklad.svg")   # w notatniku wystarczy samo schematic(uklad, sol)
print(steps(sol))                           # Markdown z $...$
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
