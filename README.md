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
| [`apps/server`](apps/server) | backend notatek (Effect): implementacja kontraktu, logowanie OAuth (arctic), Postgres przez `@effect/sql`, migracje, `/api/docs` |
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
apps/notebook ──HttpApiClient──▶ /api ──▶ apps/server ──SqlClient──▶ Postgres (devenv: 127.0.0.1:5192/electro)
      │  (@effect-atom: lista, zapis,                │  NotesRepo: zapis z rewizją
      │   otwieranie, usuwanie)                      │  (konflikt zamiast nadpisania)
      └──────────────── packages/notes-api ──────────┘  jeden kontrakt: ścieżki, schematy, błędy
```

- **Każda notatka ma swój adres.** `/` to wszystkie notatki (galeria pierwszych stron) i przykłady,
  `/notes/:ref` to notatka pobrana z serwera, a `/examples/:name` tworzy nową notatkę z przykładu.
  `ref` to slug z tytułu (`/notes/zadanie-4-mostek`) albo `id`. Po zmianie tytułu adres się zmienia,
  a stare slugi dalej prowadzą do tej samej notatki.
- **Kontrakt jest jeden.** `packages/notes-api` opisuje endpointy (`GET /api/notes/:ref`, `PUT/DELETE /api/notes/:id`,
  `GET /api/notes`), dokument (format pliku v2) i błędy (`NoteNotFound` 404, `RevisionConflict` 409,
  `NoteIdMismatch` 400). Serwer go implementuje (`HttpApiBuilder`), a notatnik woła przez klienta wygenerowanego
  z tego samego opisu (`AtomHttpApi`), więc typy i błędy zgadzają się z obu stron bez ręcznego kodu.
- **Zapis jest optymistyczny.** Klient wysyła rewizję, od której zaczął. Jeśli ktoś zapisał w międzyczasie
  (druga karta, drugi komputer), serwer zwraca konflikt, a notatnik pyta, którą wersję zostawić.
- **Serwer jest źródłem prawdy.** Strona notatki pobiera ją z serwera, a gdy serwer znika w trakcie edycji,
  zapis jest ponawiany, a przeglądarka ostrzega przed zamknięciem karty z niezapisanymi zmianami.
- **Notatki są prywatne.** Logowanie przez Google, GitHuba albo Microsoft (OAuth 2.0 z PKCE przez
  [arctic](https://arcticjs.dev)). `GET /api/auth/:provider` przekierowuje do dostawcy, a callback zakłada sesję:
  losowy token w ciasteczku `httpOnly` (w bazie tylko jego hash, ważny 30 dni). Grupa `notes` ma middleware
  `Authentication`, który bez sesji odpowiada 401. Każde zapytanie `NotesRepo` jest po `owner_id`, więc id
  i slugi są unikalne w obrębie właściciela. Ten sam zweryfikowany email od dwóch dostawców to ten sam
  użytkownik. Microsoft emaila nie weryfikuje, więc jego konta nie są łączone po emailu.
- **Dostawca jest włączony, gdy ma klucze.** `GOOGLE_CLIENT_ID` i `GOOGLE_CLIENT_SECRET` (analogicznie `GITHUB_`
  i `MICROSOFT_`) trzymasz w `.env`, który devenv wczytuje. Wzór jest w `.env.example`. Redirect URI aplikacji
  OAuth to `PUBLIC_URL/api/auth/<dostawca>/callback`, w dev `http://localhost:5190/api/auth/google/callback`.
- **Baza jest za `SqlClient`.** Postgres z devenv (`services.postgres`, dane w `.devenv/state/postgres`).
  Testy serwera i e2e zakładają w niej własny schemat i go usuwają.

`devenv up` stawia wszystko: Postgresa (:5192), notatnik (:5190), serwer notatek (:5191, dokumentacja API:
`/api/docs`) i przebudowę paczki Pythona.

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
