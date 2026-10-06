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
  `slad(q)`, `slad.at(q, t)`. Krok dobiera się sam, z błędu, który robi; `dt` to najdłuższy.
- `step_function(obwód, wartości)` — Φ: wzór klatki skompilowany raz; `phi(klatka, dt)` daje następną od
  `phi.rest`, `phi(phi.rest, ∞)` to DC, `phi.machine()` — Φ z pamięcią, które liczy całe przebiegi.

Liniowe rozwiązuje się algebrą (kroki jak na kartce), elementy „albo-albo” (dioda podręcznikowa)
przypadkami, a `exp` (dioda Shockleya, tranzystor) Newtonem.

## Jedna abstrakcja

Element to relacja swoich końców (`Rel`): końce, prawa (`Laws`) i prądy w nazwane punkty. `Laws` to monoid
(`&`: oba naraz) z trzech części — równania; wybory „albo-albo” (monada listy); log (monada Writer: co
znikło, czym i dlaczego). Wszystko inne to jedna operacja, `Laws.eliminate`:

- `f >> g` — utożsamij końce, potem `eliminate` tego, co w środku;
- rozwiązanie na kartce — `eliminate` niewiadomych, jedna po drugiej; kroki to log;
- wielkość, która znikła (`I(R_2)` wewnątrz `R_1 >> R_2`) — z logu;
- klatka (DC, AC, krok `dt`) — funktor: każde wyrażenie przez `interpret`;
- przebieg — `phi(klatka, dt)` raz po raz.

## Silnik

`numeric/engine.py` to cały silnik liczący klatki — zwykły Python, bez importów poza `math`: Newton z
ograniczaniem złącza jak w SPICE, rzadka eliminacja w kolejności wybranej przy kompilacji (`numeric/sparse.py`;
część stała liczona raz, Newton tylko na tym, czego dotyka `exp`), długość kroku z oszacowania błędu. Strona dostaje go jako JavaScript
wydrukowany z tego samego pliku przez pscript (`apps/notebook/scripts/engine_js.py`), więc obie strony
liczą tak samo. Węzły zostają niewiadomymi Newtona, a to, co się odczytuje (napięcia i prądy elementów),
liczy się po klatce prostym kodem.

## Pakiet

Foldery idą od budowy do liczb; każdy korzysta tylko z tych nad nim (plus `errors`, `values`, `parts`):

```
circuit/    budowa obwodu — nic tu nie rozwiązuje
elements/   rodzaje elementów (na circuit/)
frame/      obwód zamknięty jako równania jednej klatki (na circuit/)
numeric/    same liczby: kod, kolejność eliminacji, silnik — nie zna elementów; sympy tylko w code.py
solve/      jedna klatka rozwiązana: final (na frame/ i numeric/)
simulate.py klatka za klatką (na frame/ i numeric/)
```

| plik | co robi | korzysta z | dlaczego |
|---|---|---|---|
| `__init__.py` | to, co daje `from electro import *` | prawie wszystkiego | jedno miejsce dla użytkownika |
| `errors.py` | wyjątki z polami: `MissingData`, `Contradiction`… | `circuit/quantities` | błąd mówi, której wielkości dotyczy |
| `values.py` | `"4k7"`, `"0,5 A"`, `"230∠-120"` na liczby; wyrażenia nazw bez `eval` | — | wartości wpisuje człowiek |
| `parts.py` | części z katalogu (`part("1N4148")`) | — | parametry prawdziwych części |
| **`circuit/`** | | | |
| `algebra.py` | `Laws`: równania z pochodzeniem, wybory „albo-albo”, log; `eliminate` — jedyna operacja | `time` | jedna abstrakcja na składanie i rozwiązywanie |
| `time.py` | słowa czasu w prawach: `D` (zmiana), `Pre` (co było), `TIME`, `DT`, `THETA` | — | prawa mówią o czasie, nie wiedząc, jak się go liczy |
| `element.py` | `Rel` (końce, `Laws`, prądy w punkty: `>>` = utożsamij + `eliminate`, `@` = `&`) i `Element` (rodzaj: końcówki i prawa) | `algebra`, `time` | serce: wszystko jest elementem |
| `points.py` | punkty: `Node`, `GND`, pająki `wire`, `cap`, `cup`, `swap` | `element`, `algebra` | punkt to też element (Kirchhoff) |
| `quantities.py` | `I(e)`, `U(e)`, `P(e)`, `V(punkt)`, `Parameter(e)` | `element`, `points` | czym są dane i szukane |
| `names.py` | `"I_R_1"`, `"U_R_1 / I_R_1"` na wielkości, bez `eval` | `quantities`, `values` | nazwy pisane przez człowieka, bezpiecznie |
| **`elements/`** | rodzaje: jeden na plik, rodziny w folderach; `physics.py` — złącze p-n, poziom logiczny | `circuit/element`, `circuit/time` | nowy element = nowy plik, nic więcej |
| **`frame/`** | | | |
| `reading.py` | `Step`, `DC`, `AC`: jak `D` i `Pre` stają się równaniem jednej klatki (trapezy, Euler) | `circuit/algebra`, `circuit/time` | jedno miejsce wie, jak się liczy czas |
| `formula.py` | wzór klatki obwodu zamkniętego: nazwy jak w książce, `Laws.map` przez klatkę, dane wstawione, Kirchhoff w punktach, `eliminate`; `is_source` | `circuit/*`, `reading`, `values` | od tego miejsca nikt nie zna rodzajów elementów |
| **`numeric/`** | | | |
| `code.py` | równania klatki jako kod (reszty i niezerowe miejsca Jakobianu), Python tu, JavaScript na stronę | `circuit/algebra`, `engine`, `sparse` | sympy raz przy kompilacji, potem same liczby |
| `sparse.py` | kolejność eliminacji (Markowitz), wybrana raz; część stała osobno | — | szybkość: nie dotyka zer, nie liczy stałego dwa razy |
| `engine.py` | `Machine` (pętla klatek, krok z błędu), `System`, `newton`, `homotopy` | tylko `math` | zwykły Python, pscript drukuje go jako JS dla strony — obie liczą tak samo |
| **`solve/`** | | | |
| `final.py` | `final`: klatka DC/AC na kartce (`eliminate`, kroki z logu), przypadkami albo Newtonem; `Solution` | `frame/*`, `numeric/code`, `numeric/engine` | odpowiedź i kroki |
| **`simulate.py`** | `step_function` (Φ skompilowane raz), `simulate`, `Trace` (ślad); `RUNNER` — strona podstawia swój silnik | `frame/*`, `numeric/*`, `circuit/*` | obwód w czasie, w Pythonie i na stronie |

Droga `obwód.final(dane)`: `element.py` → `solve/final.py` → `frame/formula.py` (wzór klatki, przez
`reading.py`, potem `eliminate`) → na kartce w `final.py` (znowu `eliminate`) albo `numeric/code.py` +
`numeric/engine.py` (Newton) → `Solution`.

Droga `obwód.simulate(dane)`: `simulate.py` → `frame/formula.py` przy `Step(dt)` → `numeric/code.py`
(kod + `sparse.py`) → `numeric/engine.py` `Machine` klatka za klatką → `Trace`. Strona bierze ten sam kod
(`to_json`) i ten sam silnik, wydrukowany jako JavaScript (`apps/notebook/scripts/engine_js.py`).

Projekt i decyzje: [`DESIGN.md`](DESIGN.md). Testy: `devenv shell`, potem `pytest` w `packages/electro`.
