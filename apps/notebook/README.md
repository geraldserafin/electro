# Notatnik elektroniki

Notatnik w przeglądarce, trochę jak Colab, ale pod elektronikę. Python działa lokalnie w przeglądarce
(Pyodide w web workerze), więc nie trzeba żadnego serwera.

- **Tekst:** Markdown ze wzorami `$...$`. Dwuklik włącza edycję.
- **Kod:** Python z gotowym `electro`. Wszystkie komórki mają wspólną pamięć. Wynik ostatniego wyrażenia
  (schemat, `steps(sol)`, wzór) wyświetla się pod komórką. `Shift+Enter` uruchamia komórkę.
- **Schemat:** edytor na siatce. Kod sięga do niego przez `schemat("nazwa")`.
- **Eksport PDF:** czysty wydruk bez przycisków i siatki. Kod można ukryć przełącznikiem „kod w PDF”.

Notatnik zapisuje się automatycznie w przeglądarce. „Zapisz plik” i „Otwórz…” obsługują pliki `.electro.json`.

## Uruchomienie

```sh
pnpm install
pnpm dev            # pakuje paczki Pythona do public/py/bundle.json i startuje Vite
pnpm build          # produkcyjny build do dist/ (statyczny, można wrzucić na dowolny hosting)
```

## Testy

```sh
pnpm test:pyodide   # kernel w prawdziwym Pyodide (Node)
pnpm test:e2e       # cała aplikacja w WebKit (Playwright): start Pythona, uruchomienie, edytor
```

Testy kernela w zwykłym Pythonie (`python/test_kernel.py`) chodzą razem z resztą: `pytest` w katalogu głównym repo.

## Jak to jest zbudowane

| plik | rola |
|---|---|
| `python/electro_notebook/kernel.py` | wykonuje komórki, zamienia wyniki na wyjścia (`_repr_svg_`, `_repr_markdown_`, `_repr_latex_`) |
| `src/python/worker.ts` | ładuje Pyodide + sympy + nasze paczki (z `bundle.json`) |
| `src/python/kernel.ts` | wywołania workera jako obietnice |
| `src/schematic/` | edytor siatki; symbole bierze z `electro_render.symbol_library()`, więc wygląda jak raport |
| `src/cells/` | komórki i wyjścia |

Po zmianie kodu w `packages/` trzeba przeładować `pnpm dev`, bo `bundle.json` powstaje przy starcie.
