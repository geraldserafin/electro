# electro

Obwody elektryczne jako morfizmy **kategorii hipergrafowej** i solver, który rozwiązuje zadania krok po kroku
(każdy krok z równaniem i jego powodem) i radzi sobie z niewiadomymi, literami, prądem zmiennym i czasem.

```python
from electro import *

E, R_1, R_2, A = VoltageSource("E"), Resistor("R_1"), Resistor("R_2"), Node("A")
uklad = Problem(GND >> E >> R_1 >> A >> R_2 >> GND, {E: 12, R_1: 10, I(R_1): "500m"}, [Parameter(R_2)])

sol = solve(uklad)
sol(Parameter(R_2))   # 14
sol(V(A))             # 7
sol("U_R_1 / I_R_1")  # 10 — po nazwach też, wyrażenia bez eval
sol.steps             # co wyliczono, z którego równania i dlaczego
```

Obwód to sama budowa, bez liczb; liczby i pytania dochodzą w **zadaniu** (`Problem`). Ten sam obwód
rozwiązuje się z różnymi danymi, a analizy (prąd stały, wskazy, czas) tylko inaczej czytają te same prawa.

Biblioteka nie mówi nic słowami: `solve` daje `Solution` — wartości i kroki (`SolutionStep`: co
znaleziono, z jakiego równania, skąd to równanie), a to, co poszło nie tak, to wyjątki z polami
(`MissingData`, `Contradiction`…). `latex` drukuje je ładnie (`Solution` też sam, w Jupyterze). Słowami
mówi ten, kto pokazuje wynik — notatnik po polsku albo po angielsku.

## Klocki

Każdy obwód ma typ `m → n`: `m` końców z lewej, `n` z prawej. Element ma nazwę; jego tożsamość to ten obiekt.

| zapis | znaczenie |
|---|---|
| `Resistor("R_1")`, `Capacitor`, `Inductor` | elementy dwukońcowe, 1 → 1 |
| `VoltageSource`, `CurrentSource`, `SineSource`, `SquareSource` | źródła (`+` na drugim końcu; prąd pchany od pierwszego do drugiego) |
| `Ammeter`, `Voltmeter` | idealne mierniki; odczyt to dana `I(A_1)`, `U(V_1)` |
| `OpAmp`, `VCVS`, `VCCS`, `CCVS`, `CCCS`, `Transformer`, `Coupled` | wielokońcowe: `at(e, a, b, c…)` |
| `Diode`, `LED`, `Zener`, `NPN`, `PNP`, `NMOS`, `PMOS`, bramki, `Timer555`, `Motor`, `Relay`, płytki… | nieliniowe i z pamięcią: w czasie |
| `Hole` | nieznany element: `fill` wstawia najprostszy pasujący |
| `f >> g` | szeregowo (złożenie) |
| `f \| g` | równolegle |
| `f @ g` | obok siebie, bez połączenia (iloczyn monoidalny) |
| `Node("A")`, `GND` | punkt (ten sam obiekt w dwóch miejscach = jeden punkt), masa |
| `loop(a, b, …)`, `close(f)` | pętla |
| `flip(f)` | odwrócony (transpozycja przez `cap` i `cup`) |
| `at(e, a, b)`, `beside(…)` | element między punktami, kawałki obok siebie — dowolny graf (mostek) |
| `wire`, `cap`, `cup` | pająki: 1 → 1, 0 → 2, 2 → 0 |

Wartości: `10`, `4.7`, `"4.7k"`, `"4k7"`, `"0,5 A"`, `"230∠-120"`, `"R"` (litera). Element o kilku
parametrach dostaje słownik: `{S: {"": 10, "f": 50}}`, `{D: part("1N4148")}`.

## Zadanie i rozwiązanie

```python
Problem(obwod, given={element: wartość, wielkość: wartość}, find=[wielkość, …])
```

Wielkości: `I(e)`, `U(e)`, `P(e)`, `Parameter(e)`, `V(punkt)`, `U(a, b)`; dana może też być inną wielkością
(`U(R_1): 2 * U(R_2)`). `solve(zadanie)` zwraca `Solution`: `sol(q)`, `sol.answers` (szukane), `sol.steps`.
Czego nie da się wyznaczyć — `MissingData` (ile danych brakuje i które by wystarczyły); dane sprzeczne —
`Contradiction` (które się wykluczają); dwa rozwiązania — `Ambiguous`.

Prąd zmienny: `solve(zadanie, AC(ω))` — wskazy przy ω; `settled(zadanie)` to `AC` przy częstotliwości
sinusów zadania (albo DC). AC to też klatka: klatki bez końca, każda to poprzednia obrócona o ω·dt;
solver nie wie nic o AC ani o żadnym elemencie — zamienia tylko prawa na wzór klatki (`methods/ac.py`). W czasie: `simulate(zadanie, until=…, dt=…, inputs={…})` zwraca ślad:
`slad(q)`, `slad.at(q, t)`, `slad.spectrum(q)`. `solve` to jedna klatka: DC to klatka nieskończenie długa (`DC()` = `Step(∞)`, wszystko ustalone),
`solve(zadanie, Step(dt), before=poprzednia)` — klatka `dt` po poprzedniej (domyślnie od spoczynku).
Symulacja to nic więcej niż klatki jedna po drugiej; `simulate` liczy je skompilowane raz: `phi =
step_function(zadanie)`, `phi(klatka, dt)` daje następną od `phi.rest`, `phi(phi.rest, ∞)` to DC, a dla
obwodu liniowego `phi.formula(V(A))` to krok jako wzór (`V_A⁻` — krok wcześniej).

## Metody

| | |
|---|---|
| `blackbox(kawałek)`, `resistance(…)`, `matches(…, Kind)` | kawałek 1 → 1 widziany z końców: relacja, jaki to jeden element |
| `thevenin(between(zadanie, A, B))` | Thévenin widziany z dwóch punktów |
| `superposition(zadanie, q)` | wkład każdego źródła z osobna |
| `simplify(zadanie)` | upraszczanie jak w zeszycie, krok po kroku |
| `fill(zadanie, dziura)` | najprostszy element w miejsce `Hole` |
| `respond`/`responses`, `sweep`/`sweeps`, `tolerance`/`spreads` | charakterystyka częstotliwościowa, przemiatanie wartości, rozrzut z tolerancji — każde rozwiązane raz, z literą |
| `to_spice`, `from_spice` | netlisty SPICE w obie strony (porównane z ngspice w testach) |
| `to_netlist`, `from_netlist` | zadanie jako dane (tak rozmawia z nim notatnik) |
| `step_function` | `solve` jednej klatki skompilowane (Φ); `to_json()` dla silnika na stronie |

## Pakiet

| | |
|---|---|
| `circuit/` | budowa: drzewo, netlista (kospan), rodzaje elementów i ich prawa, części z katalogów |
| `problem/` | zadanie: wielkości, dane, nazwy, netlista jako dane, SPICE |
| `solver/` | równania z praw, rozwiązanie krok po kroku, przypadki; liczbami: równania jako kod i Newton |
| `methods/` | metody nad solverem, bez nowych praw |
| `simulation/` | Φ (`solver/step.py`) powtarzane: jak długi krok, przebieg, wejścia |
| `latex.py` | rozwiązanie, wielkości i wartości w LaTeX |
| `values.py` | liczby z jednostkami i przedrostkami, wyrażenia bez `eval` |

Projekt i decyzje: [`DESIGN.md`](DESIGN.md). Testy: `devenv shell`, potem `pytest` w katalogu głównym repo.
