# electro

Obwody elektryczne jako morfizmy **kategorii hipergrafowej** i solver, który rozwiązuje je krok po kroku
(każdy krok z równaniem i jego powodem) — z niewiadomymi, literami, prądem zmiennym i w czasie.

```python
from electro import *

E, R_1, R_2, A = VoltageSource("E"), Resistor("R_1"), Resistor("R_2"), Node("A")
uklad = GND >> E >> R_1 >> A >> R_2 >> GND

sol = uklad.final({E: 12, R_1: 10, I(R_1): "500m"})
sol(Parameter(R_2))   # 14
sol(V(A))             # 7
sol("U_R_1 / I_R_1")  # 10 — po nazwach też, wyrażenia bez eval
sol.steps             # co wyliczono, z którego równania i dlaczego

uklad.simulate({E: 12, R_1: 10, R_2: 14}, until=1)   # klatka po klatce
```

Obwód to sama budowa, bez liczb; liczby dochodzą, gdy się go rozwiązuje. Biblioteka nie mówi nic słowami:
`final` daje `Solution` — wartości i kroki (`SolutionStep`: co znaleziono, z jakiego równania, skąd to
równanie), a to, co poszło nie tak, to wyjątki z polami (`MissingData`, `Contradiction`, `Ambiguous`…).
Słowami mówi ten, kto pokazuje wynik — notatnik po polsku albo po angielsku.

## Klocki

Wszystko jest `Element`em: opornik, `E >> R`, każdy obwód. Element to relacja swoich końców (na każdym
potencjał i prąd) i prawa między nimi. Rodzaj elementu to podklasa `Element` z końcówkami i prawami —
jedna na plik (`elements/`, rodziny w folderach: `diodes/`, `transistors/`…).

| zapis | znaczenie |
|---|---|
| `Resistor("R_1")`, `Capacitor`, `Inductor` | elementy dwukońcowe, 1 → 1 |
| `VoltageSource`, `CurrentSource`, `SineSource`, `SquareSource` | źródła (`+` na drugim końcu; prąd pchany od pierwszego do drugiego) |
| `Ammeter`, `Voltmeter` | idealne mierniki; odczyt to dana `I(A_1)`, `U(V_1)` |
| `OpAmp`, `VCVS`, `VCCS`, `CCVS`, `CCCS`, `Transformer`, `Coupled` | wielokońcowe, 0 → n: `T >> (a @ b @ c)` (niewyrysowany `gnd` — na masie, bez końca) |
| `Diode`, `LED`, `Zener`, `NPN`, `PNP`, `NMOS`, `PMOS`, bramki, `Timer555`, `Motor`, `Relay`, płytki… | nieliniowe i z pamięcią |
| `Hole` | nieznany element |
| `f >> g` | szeregowo: końce sklejone, a to, co w środku, od razu wyeliminowane |
| `f \| g` | równolegle |
| `f @ g` | obok siebie, bez połączenia |
| `~f` | zamknięty: dwa końce połączone (pętla: `~(E >> R_1 >> R_2)`) |
| `-f` | odwrócony |
| `Node("A")`, `GND` | punkt (ten sam obiekt w dwóch miejscach = jeden punkt), masa |
| `wire`, `cap`, `cup`, `swap` | pająki 1 → 1, 0 → 2, 2 → 0 i skrzyżowanie 2 → 2 |

`print(R_1 >> R_2)` pokazuje prawo na końcach: `U = I*(R_1 + R_2)` — opór zastępczy wychodzi ze
składania, nikt nie mówi o „szeregowo”. Element ma nazwę; jego tożsamość to ten obiekt.

Wartości: `10`, `4.7`, `"4.7k"`, `"4k7"`, `"0,5 A"`, `"230∠-120"`, `"R"` (litera). Element o kilku
parametrach dostaje słownik: `{S: {"": 10, "f": 50}}`, `{D: part("1N4148")}`. Dana może też być
wielkością: `I(e)`, `U(e)`, `P(e)`, `Parameter(e)`, `V(punkt)`, `U(a, b)`, także inną wielkością
(`U(R_1): 2 * U(R_2)`).

## Klatka

Obwód zamknięty (bez wolnych końców) to same prawa. Solver zamienia je na **wzór klatki** i nic więcej
nie wie o elementach: `D(x)` w klatce długości `dt` to `(x − x⁻)/dt`, `Pre(x)` to `x⁻`.

- `obwód.final(wartości)` — klatka, do której obwód dochodzi: nieskończenie długa (DC = `Step(∞)`), a z
  sinusami jednej częstotliwości — obracająca się (`AC(ω)`, wskazy); `final(wartości, AC(ω))` przy danej ω.
- `obwód.simulate(wartości, until=…, dt=…, inputs={…})` — klatki jedna po drugiej, od spoczynku; ślad:
  `slad(q)`, `slad.at(q, t)`, `slad.spectrum(q)`.
- `step_function(obwód, wartości)` — Φ: wzór klatki skompilowany raz; `phi(klatka, dt)` daje następną od
  `phi.rest`, `phi(phi.rest, ∞)` to DC, `phi.machine()` — Φ z pamięcią, które liczy całe przebiegi.

Liniowe rozwiązuje się algebrą (kroki jak na kartce), elementy „albo-albo” (dioda podręcznikowa)
przypadkami, a `exp` (dioda Shockleya, tranzystor) Newtonem.

## Silnik

`engine.py` to cały silnik liczący klatki — zwykły Python, bez importów poza `math`: Newton z
ograniczaniem złącza jak w SPICE, eliminacja Gaussa, długość kroku. Strona dostaje go jako JavaScript
wydrukowany z tego samego pliku przez pscript (`apps/notebook/scripts/engine_js.py`), więc obie strony
liczą tak samo. Węzły zostają niewiadomymi Newtona, a to, co się odczytuje (napięcia i prądy elementów),
liczy się po klatce prostym kodem.

## Pakiet

| | |
|---|---|
| `element.py` | `Element`, relacja, składanie i eliminacja |
| `points.py` | pająki, `Node`, `GND` |
| `elements/` | rodzaje elementów, jeden na plik |
| `formula.py` | wzór klatki obwodu zamkniętego: nazwy, dane, co zostało do rozwiązania |
| `frame.py`, `time.py` | klatki (`Step`, `DC`, `AC`) i słowa czasu (`D`, `Pre`) |
| `solve.py`, `by_hand.py` | `final`: klatka rozwiązana algebrą, przypadkami albo Newtonem; `Solution` |
| `simulate.py`, `code.py`, `engine.py` | Φ skompilowane, przebieg, ślad |
| `laws.py` | co wynika z praw elementu: źródło, miernik, pamięć |
| `quantities.py`, `names.py`, `values.py` | wielkości, nazwy, wartości z jednostkami |
| `parts.py` | części z katalogów |

Projekt i decyzje: [`DESIGN.md`](DESIGN.md). Testy: `devenv shell`, potem `pytest` w `packages/electro`.
