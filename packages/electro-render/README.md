# electro-render

Wygląd obwodów. Pozycje pochodzą z `electro-schematic`: z rysunku na siatce albo z auto-layoutu kodu.
Ta paczka tylko je rysuje.

```python
from electro_render import schematic, steps, symbol_library_json

schematic(uklad)                  # obwód z kodu: auto-layout + SVG
schematic(sch, sol)               # rysunek z siatki + prądy (strzałka w prawdziwym kierunku) i napięcia
steps(sol)                        # rozwiązanie krok po kroku: Markdown + LaTeX
symbol_library_json()             # te same symbole dla edytora w przeglądarce
```

## Biblioteka symboli

`symbols.py` to jedyne miejsce, które mówi, jak wygląda rezystor, źródło itd.
Każdy symbol to SVG z pierwszym pinem w (0, 0), w pikselach (20 px na kratkę).
Edytor webowy bierze je z `symbol_library_json()`, więc renderer w Pythonie i edytor rysują identycznie.

## Konwencje

- Etykieta stoi nad elementem poziomym albo na lewo od pionowego. Wyniki stoją po drugiej stronie.
- Ujemny prąd rysowany jest strzałką w drugą stronę z dodatnią wartością. Napięcie jest odwracane razem z nim.
- Kropka węzła pojawia się tam, gdzie spotykają się co najmniej trzy przewody lub piny.
