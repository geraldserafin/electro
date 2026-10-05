# Notatnik elektroniki

Notatnik w przeglądarce, trochę jak Colab, ale pod elektronikę. Python działa lokalnie w przeglądarce
(Pyodide w web workerze), więc nie trzeba żadnego serwera.

- **Tekst:** Markdown ze wzorami `$...$`. Dwuklik włącza edycję.
- **Kod:** Python z gotowym `electro`. Wszystkie komórki mają wspólną pamięć. Wynik ostatniego wyrażenia
  (zadanie jako schemat, rozwiązanie krok po kroku, wykres, wzór) wyświetla się pod komórką; obrazki rysuje
  strona, Python oddaje tylko dane. `Shift+Enter` uruchamia komórkę.
- **Schemat:** edytor na siatce w stylu Excalidraw. Na górze pasek narzędzi ze skrótami (V, W, 1–0), po prawej
  „Kod” i „Symuluj”, na dole powiększenie, cofanie i pomoc. ▶ liczy prądy i napięcia i pokazuje je przy
  elementach; ⚡ uruchamia obwód w czasie. Schemat jest w kodzie zmienną o swojej nazwie (zadaniem `Problem`),
  też przez `schemat("nazwa")`.
- **Eksport PDF:** czysty wydruk bez przycisków i siatki. Kod można ukryć przełącznikiem „kod w PDF”.

Notatnik zapisuje się automatycznie w przeglądarce. „Zapisz plik” i „Otwórz…” obsługują pliki `.electro.json`.

**Kursy i przykłady** (na stronie głównej) to foldery w `examples/<kurs>/`: `course.json` (tytuł i opis)
i lekcje `NN-nazwa.electro.json`. Lekcja otwiera się do czytania i próbowania, z zapisanymi wynikami
(`/examples/<kurs>/<lekcja>`): zmiany się nie zapisują, dopóki nie dodasz jej do notatek; cały kurs
można dodać do notatek jako folder. Lekcje generują skrypty
w `scripts/examples/` (`python apps/notebook/scripts/examples/make.py` z katalogu głównego, w devenv shell):
Python zapisuje lekcje jako dane, a `run.ts` uruchamia je jak „Uruchom wszystko” (jądro w Pyodide) i sprawdza
każdy schemat (obwód, symulacja w czasie, połączenia).
`python/test_examples.py` pilnuje, że każda komórka działa, a `examples.test.ts` — że każdy szkic się kompiluje.

## Uruchomienie

Najprościej z katalogu głównego repo:

```sh
devenv up           # notatnik na http://localhost:5190, bundle Pythona przebudowuje się przy każdej zmianie
```

Albo ręcznie w `apps/notebook`:

```sh
pnpm install
pnpm dev            # pakuje paczki Pythona do public/py/bundle.json i startuje Vite (port 5190)
pnpm build          # produkcyjny build do dist/ (statyczny, można wrzucić na dowolny hosting)
```

## Testy

```sh
pnpm test:pyodide   # kernel w prawdziwym Pyodide (Node)
pnpm test:examples  # każdy przykład uruchomiony od nowa jak „Uruchom wszystko”
pnpm test:e2e       # cała aplikacja w WebKit (Playwright): start Pythona, uruchomienie, edytor
```

Testy kernela w zwykłym Pythonie (`python/test_kernel.py`) chodzą razem z resztą: `pytest` w katalogu głównym repo.

## Jak to jest zbudowane

Front jest pocięty na warstwy; każda importuje tylko z warstw pod sobą:

```
src/app/        wejście (main.tsx: routing), style globalne
src/pages/      strony pod adresami — składają funkcje w całość (Home, NotePage, ExamplePage)
src/features/   pionowe plastry: każdy ma swoje komponenty, stan i logikę
src/shared/     to, co nie wie o żadnej funkcji: model notatki (typy, format pliku), ui (ikony, Markdown, szkielety)
```

Plaster z innego plastra bierze tylko to, co ten wystawia w swoim `index.ts` (`@/features/schematic`,
nie `@/features/schematic/Editor`); wewnątrz plastra importy są względne. `@/` to `src/`.

| plaster | rola |
|---|---|
| `features/notebook/` | edycja notatki: komórki (`cells/`), spis treści, tytuł |
| `features/notes/` | notatki na serwerze: lista, zapis i konflikty, galeria |
| `features/schematic/` | edytor siatki (`Editor`: stan i gesty; wyspy wokół planszy to osobne komponenty; `useCamera`, `useHistory`: widok i cofanie; styl samego rysunku SVG w `Canvas.css`); `symbols.json` to wygląd elementów (edytor, obrazki w komórkach, PDF); widać go, zanim Python się załaduje |
| `features/python/` | `worker.ts` ładuje Pyodide + sympy + `electro` i jądro (z `bundle.json`), `kernel.ts` — wywołania workera jako obietnice, `outputs.ts` — co komórka dostaje (zadania ze schematów) i co pokazuje (schemat ułożony i narysowany, wykres) |
| `features/pdf-export/` | eksport do PDF: dialog (`usePreview`: skład po każdej zmianie i strony jako obrazki), ustawienia, Typst w workerze; PDF jest w języku aplikacji (dzielenie wyrazów, tytuł spisu treści, data) |
| `features/examples/` | przykładowe notatki |
| `features/solution/` | co mówi solver: typy z Pythona (błędy, ostrzeżenia, powody kroków, rozwiązanie krok po kroku — `shared/model/issues.ts`) słowami, w języku czytającego; też w PDF |
| `features/theme/`, `features/language/` | motyw (jasny / ciemny / systemowy) i język (PL / EN): wybór, zapamiętany w przeglądarce, i jego grupa w menu |
| `features/settings/` | menu ⋯ w prawym górnym rogu (strona główna i notatka): motyw i język |
| `python/electro_notebook/` | (Python) cienkie jądro: `kernel.py` to to, co woła worker; `cells.py` wykonuje komórki i zamienia wyniki na wyjścia jako dane, `board.py` to przyciski schematu, `code_view.py` widok kodu, `ai.py` narzędzie AI, `task.py` zadania, `errors.py` błędy jako dane |

**Style.** Tailwind v4 (`src/app/styles.css`). Kolory to wyłącznie tokeny aplikacji (`bg-surface`, `text-muted`,
`border-line`…; jasne i ciemne wartości są w `src/app/tokens.css`). Klasy składa się przez `cn()` (`shared/lib/cn`: clsx +
tailwind-merge) — z dwóch klas na tę samą właściwość wygrywa wtedy późniejsza; bez niego o wyniku decyduje kolejność
w CSS Tailwinda, nie w atrybucie. To, czego nie da się sensownie zapisać klasami (np. miniatura strony PDF, która
przestawia tokeny i styluje cudzy Markdown), leży obok komponentu jako `*.css` w `@layer components`.

Elementy zaczynają od resetu Tailwinda (preflight): przycisk, pole czy nagłówek wygląda tak, jak mówią jego klasy —
style bazowe to tylko `body`, kursor przycisków i kolor podpowiedzi w polach. Markdown dostaje z powrotem odstępy
i rozmiary dokumentu w `Markdown.css`.

Testy e2e szukają elementów po rolach, etykietach i atrybutach `data-*` (np. `data-cell`, `data-output`), nie po klasach.

**Języki.** i18next: każdy plaster ma `messages.ts` (`pl` i `en` o tym samym kształcie — pilnuje TypeScript) jako
swoją przestrzeń nazw; `src/app/i18n.ts` je zbiera. Język wybiera się w menu ⋯; wybór zostaje w przeglądarce,
a przed wyborem — język przeglądarki (angielski, gdy nie zna żadnego z naszych). Testy e2e chodzą z `pl-PL`.

Python nie mówi nic słowami: to, co poszło nie tak, to typ (`electro.issues`, np. `MissingData(targets, needed,
options)`), powód kroku rozwiązania też (`electro.reasons`, np. `OhmsLaw(label)`), a `steps(sol)` to dane.
Kernel wysyła je jako JSON (`{"type": "MissingData", …}`, wzory w LaTeX), a `features/solution` mówi je po polsku
albo po angielsku — nowy typ w Pythonie bez tłumaczenia to błąd TypeScriptu. Błędy samego Pythona (`NameError`…)
zostają jego słowami.

Przy `devenv up` zmiany w `packages/` wystarczy odświeżyć w przeglądarce. Przy samym `pnpm dev` `bundle.json` powstaje tylko przy starcie (albo użyj `pnpm python --watch`).

## Plik notatnika `*.electro.json` (wersja 2)

Czyta go i zapisuje `src/shared/model/format.ts` (odczyt migruje starsze wersje i sprawdza kształt).

```json
{
  "format": "electro-notebook", "version": 2,
  "id": "5f0c…", "title": "Sprawozdanie",
  "created": "2026-09-27T12:00:00Z", "modified": "2026-09-27T12:30:00Z",
  "settings": {"codeInPdf": true},
  "cells": [
    {"id": "a1", "type": "markdown", "source": "# Cel"},
    {"id": "b2", "type": "code", "source": "układ1.solve()", "outputs": [], "execution": 3},
    {"id": "c3", "type": "schematic", "name": "Układ 1",
     "schematic": {"elements": [], "wires": []}, "view": "schematic", "results": {}, "problems": [], "stale": false}
  ]
}
```

- **`id`** notatnika jest stałe między zapisami — po nim serwer rozpozna notatkę. Otwarty przykład dostaje nowe.
- Dokumentem jest treść komórek (`source`, `name`, `schematic`). `outputs`, `execution`, `results`, `problems`,
  `stale`, `view` to ślad ostatniego uruchomienia i edytora — zapisany, żeby plik otwierał się tak, jak go zostawiono;
  
- Pola, których ta wersja nie zna, są zachowywane przy odczycie i zapisie — plik z nowszej wersji aplikacji
  nie traci niczego w starszej.
- Wersja 1 (bez `format`, `id`, dat i `settings`; w schematach pole pomiarów i tabela wyników) jest migrowana.
  Plik w wersji nowszej niż znana daje czytelny błąd zamiast zgadywania.
