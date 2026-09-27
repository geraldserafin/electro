# electro-schematic

Obwód narysowany na siatce. To ta sama rzecz co `net(...)`, tylko węzły wynikają ze współrzędnych:
piny i końce przewodów w tym samym punkcie siatki są połączone.

```python
from electro_schematic import Schematic, Element, Wire, layout

sch = layout(uklad)                      # kod → rysunek (auto-layout)
sch.move("A_1", (6, 3))                  # przewody idą za elementem
sch.rotate("E_1", 180)                   # odwrócenie źródła = obrót o 180°
text = sch.to_json()                     # zapis (np. w komórce notatnika)
sol = Schematic.from_json(text).to_circuit().solve(I_A_1=0, find="R_2")
```

## Model

| pole | znaczenie |
|---|---|
| `Element.id` | stała tożsamość; dla elementów to też etykieta (`R_1`), więc przesuwanie nic nie przenumerowuje |
| `Element.kind` | `resistor`, `capacitor`, `inductor`, `voltage_source`, `current_source`, `ammeter`, `voltmeter`, `hole`, `opamp`, `ground`, `label`, `terminal` |
| `Element.at`, `rotation` | pierwszy pin na siatce, obrót o 0/90/180/270° zgodnie z ruchem wskazówek |
| `Element.value` | wartość jak wpisana: `"4.7k"`, `"R"` (symbol), `None` (niewiadoma) |
| `Element.text` | nazwa węzła dla `label` (ta sama nazwa = ten sam węzeł) |
| `Wire.points` | łamana z odcinków poziomych i pionowych |

## Zasady połączeń

- Piny i końce przewodów w tym samym punkcie są połączone.
- Koniec przewodu (albo pin) leżący na środku innego przewodu to rozgałęzienie typu T.
- Przewody, które się tylko krzyżują, **nie** są połączone.
- `ground` to masa, a `label` łączy węzły po nazwie.

`KINDS` mówi tylko o pinach i o tym, który element z `electro` stoi za danym rodzajem.
Wygląd należy do `electro-render`.
