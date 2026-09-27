# electro

Notatnik do elektroniki: obwody jako kod, solver z rozwiązaniem krok po kroku,
schematy, a docelowo notatnik webowy z eksportem sprawozdań do PDF.

| katalog | co to jest |
|---|---|
| [`packages/electro`](packages/electro) | rdzeń: obwody jako morfizmy kategorii, kombinatory `+`/`\|`, solver, `find`, `Hole` |
| [`packages/electro-schematic`](packages/electro-schematic) | rysunek na siatce: model (JSON), rysunek → obwód, auto-layout kodu, edycja (`move`, `rotate`) |
| [`packages/electro-render`](packages/electro-render) | wygląd: biblioteka symboli (też jako JSON dla edytora), schemat → SVG, ślad rozwiązania → Markdown + LaTeX |
| [`packages/electro-notes`](packages/electro-notes) | plik notatnika `*.electro.json`: odczyt, zapis, migracja starszych wersji, walidacja, `python -m electro_notes check` |
| [`packages/notes-api`](packages/notes-api) | kontrakt front ↔ backend notatek (TypeScript): schematy Effect Schema i `HttpApi` z błędami |
| [`apps/server`](apps/server) | backend notatek (Effect): implementacja kontraktu, SQLite przez `@effect/sql`, migracje, `/api/docs` |
| [`apps/notebook`](apps/notebook) | notatnik w przeglądarce (React + Pyodide): Markdown, kod, edytor schematów na siatce, eksport PDF |

```
electro  ◀──  electro-schematic  ◀──  electro-render  ◀──  apps/notebook (Pyodide + edytor w TS)
solver        gdzie co leży     ▲      jak to wygląda              │ ten sam format pliku
                                └──  electro-notes  ◀──────────────┘
```

```python
from electro import *
from electro_render import schematic, steps

uklad = supply(12) + Resistor(10) + node("A") + shunt(Resistor()) + Resistor(5) + ground
sol = uklad.solve(I_R_1=1, find="R_2")

schematic(uklad, sol).save("uklad.svg")   # w notatniku wystarczy samo schematic(uklad, sol)
print(steps(sol))                           # Markdown z $...$
```

## Notatki na serwerze

```
apps/notebook ──HttpApiClient──▶ /api ──▶ apps/server ──SqlClient──▶ SQLite (.data/notes.sqlite)
      │  (@effect-atom: lista, zapis,                │  NotesRepo: zapis z rewizją
      │   otwieranie, usuwanie)                      │  (konflikt zamiast nadpisania)
      └──────────────── packages/notes-api ──────────┘  jeden kontrakt: ścieżki, schematy, błędy
```

- **Kontrakt jest jeden.** `packages/notes-api` opisuje endpointy (`GET/PUT/DELETE /api/notes/:id`,
  `GET /api/notes`), dokument (format pliku v2) i błędy (`NoteNotFound` 404, `RevisionConflict` 409,
  `NoteIdMismatch` 400). Serwer go implementuje (`HttpApiBuilder`), a notatnik woła przez klienta wygenerowanego
  z tego samego opisu (`AtomHttpApi`), więc typy i błędy zgadzają się z obu stron bez ręcznego kodu.
- **Zapis jest optymistyczny.** Klient wysyła rewizję, od której zaczął. Jeśli ktoś zapisał w międzyczasie
  (druga karta, drugi komputer), serwer zwraca konflikt, a notatnik pyta, którą wersję zostawić.
- **Offline działa dalej.** Gdy serwer jest niedostępny, notatnik zapisuje się w przeglądarce
  i ponawia wysyłkę.
- **Jeden użytkownik (na razie).** Tabela `notes` nie ma jeszcze `user_id`. Użytkownicy dojdą jako middleware
  uwierzytelniania na grupie `notes` i kolumna w kluczu. Adresy API się nie zmienią.
- **Baza jest za `SqlClient`.** Przejście z SQLite na Postgresa to wymiana warstwy w `apps/server/src/Database.ts`.

`devenv up` stawia wszystko: notatnik (:5190), serwer notatek (:5191, dokumentacja API: `/api/docs`)
i przebudowę paczki Pythona.

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
