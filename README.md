# electro

Notatnik do elektroniki: obwody jako kod, solver z rozwiązaniem krok po kroku,
schematy, a docelowo notatnik webowy z eksportem sprawozdań do PDF.

| katalog | co to jest |
|---|---|
| [`packages/electro`](packages/electro) | rdzeń: obwody jako morfizmy kategorii, kombinatory `+`/`\|`, solver, `find`, `Hole` |
| [`packages/electro-schematic`](packages/electro-schematic) | rysunek na siatce: model (JSON), rysunek → obwód, auto-layout kodu, edycja (`move`, `rotate`) |
| [`packages/electro-render`](packages/electro-render) | wygląd: biblioteka symboli (też jako JSON dla edytora), schemat → SVG, ślad rozwiązania → Markdown + LaTeX |
| [`packages/electro-notes`](packages/electro-notes) | plik notatnika `*.electro.json`: odczyt, zapis, migracja starszych wersji, walidacja, `python -m electro_notes check` |
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
