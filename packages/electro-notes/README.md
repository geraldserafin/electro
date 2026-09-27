# electro-notes

Plik notatnika electro, `*.electro.json` — ten sam format w notatniku webowym (`apps/notebook/src/format.ts`),
w Pythonie i (docelowo) na serwerze z notatkami użytkowników.

```python
from electro_notes import Notebook, load

nb = load("sprawozdanie.electro.json")      # starsze wersje pliku są migrowane przy odczycie
nb.schematic("Układ 1").solve(find="E")     # schemat po nazwie (albo zmiennej: "układ1") to obwód
nb.add_code("układ1.solve()")
nb.save("sprawozdanie.electro.json")

nb = Notebook("Zadanie 4")                  # albo od zera
nb.add_markdown("# Zadanie 4")
nb.add_schematic("Układ 1", loop(VoltageSource(), Resistor(3)))   # obwód układa się sam na siatce
```

```
python -m electro_notes check  plik.electro.json …   # co jest w pliku, albo gdzie jest zepsuty
python -m electro_notes upgrade plik.electro.json …  # zapisz w bieżącej wersji formatu
python -m electro_notes strip  plik.electro.json …   # bez wyników uruchomień (np. do gita)
```

## Format (wersja 2)

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
  `strip` go usuwa.
- Pola, których ta wersja nie zna, są zachowywane przy odczycie i zapisie — plik z nowszej wersji aplikacji
  nie traci niczego w starszej.
- Wersja 1 (bez `format`, `id`, dat i `settings`; w schematach pole pomiarów i tabela wyników) jest migrowana.
  Plik w wersji nowszej niż znana daje czytelny błąd zamiast zgadywania.
