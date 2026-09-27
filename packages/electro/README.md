# electro

Obwody elektryczne jako morfizmy **kategorii hipergrafowej** + solver, który rozwiązuje
zadania krok po kroku (z uzasadnieniem każdego kroku) i radzi sobie z niewiadomymi.

```python
from electro import *

c = supply(12) + Resistor(10) + Resistor() + ground      # Resistor() = niewiadoma
sol = c.solve(I_R1=0.5)

sol["R2"]          # R2 = 14 Ω   U = 7 V   I = 500 mA   P = 3.5 W
print(sol.explain())
```

```
Dane:
  E1 = 12 V
  R1 = 10 Ω
  I_R1 = 500 mA
Rozwiązanie:
  1. U_E1 = E1 = 12 V   — źródło napięcia (E1)
  2. U_R1 = I_R1·R1 = 0.5·10 = 5 V   — prawo Ohma (R1)
  ...
  8. R2 = U_R2/I_R2 = 7/0.5 = 14 Ω   — prawo Ohma (R2)
```

## Klocki i kombinatory

Każdy obwód ma typ `m → n`: `m` zacisków z lewej, `n` z prawej.

| zapis | typ | znaczenie |
|---|---|---|
| `Resistor(10)`, `Capacitor("1u")`, `Inductor("2m")` | 1 → 1 | elementy; `Resistor()` = niewiadoma, `Resistor("R")` = symbol |
| `VoltageSource(12)`, `CurrentSource("0,5")` | 1 → 1 | źródło napięcia (`+` z prawej), źródło prądu (pcha w prawo) |
| `Ammeter(odczyt)`, `Voltmeter(odczyt)` | 1 → 1 | idealne mierniki; odczyt to dana pomiarowa, bez niego — wynik do policzenia |
| `OpAmp()` | 2 → 1 | idealny wzmacniacz operacyjny: (+, −) → wyjście |
| `Hole()` | 1 → 1 | nieznany element; solver dobiera najprostszy pasujący |
| `wire`, `wires(n)`, `swap` | | przewody, skrzyżowanie |
| `split`, `join`, `spider(m, n)` | | węzeł (pająk Frobeniusa) |
| `ground` / `ground.transpose()` | 1 → 0 / 0 → 1 | masa |
| `node("A")` | 1 → 1 | nazwany punkt (ta sama nazwa = ten sam węzeł) |
| `f + g` | | szeregowo (złożenie) |
| `f \| g` | | równolegle; `a + b \| c` znaczy `(a + b) \| c` (priorytety Pythona) |
| `f @ g` | | obok siebie, bez połączenia (iloczyn monoidalny) |
| `f.transpose()` | | transpozycja (sztylet): zamiana lewej i prawej strony; dla źródła zmiana biegunowości |
| `f.close()`, `loop(...)` | n → n ⇒ 0 → 0 | zamknięcie w pętlę (ślad) |
| `shunt(x)` | 1 → 1 | element od linii do masy |
| `supply(v)` | 0 → 1 | `ground.transpose() + VoltageSource(v)` |
| `net((x, "A", "B"), ...)` | 0 → 0 | dowolny graf, np. mostek (netlista jak w SPICE) |

Etykieta jest opcjonalna: `Resistor(10)` dostanie nazwę automatycznie (R1, R2, …),
`Resistor(10, label="Rx")` własną.

Wartości: `10`, `4.7`, `"4.7k"`, `"4k7"`, `"0,5 A"`, `"12V"`, `"R"` (symbol).

## Rozwiązywanie

```python
sol = c.solve(I_R1=0.5)                    # dane jako kwargs
sol = c.solve({I("R1"): "500m"})           # albo słownik
sol = c.solve(Eq(U("R1"), 2 * U("R2")))    # albo dowolne równanie
sol = c.solve(P_R1=8)                      # moc P = U·I

sol["R1"].I, sol.V("A"), sol.U("A", "B"), sol(U("R1") / I("R1"))
print(sol.explain())                       # ślad rozwiązania
```

### Zadanie typu „dane są…, oblicz X, Y, Z”

```python
sol = uklad.solve(I_R_1=2, U_R_2=8, U_R_3=5, find=["R_1", "R_3", "E_2"])
sol                  # R_1 = 2 Ω, R_3 = 5 Ω, E_2 = -3 V
sol.answers          # {"R_1": 2, "R_3": 5, "E_2": -3}
print(sol.explain()) # tylko kroki potrzebne do odpowiedzi + „Odpowiedź:”
```

Etykieta w `find` oznacza wartość elementu (`"R_1"` → rezystancja). Każda inna nazwa to wielkość
(`"I_R_2"`, `"U_R_1"`, `"V_A"`). Gdy danych brakuje, dostajesz `MissingData` z informacją,
czego brakuje:

```
Nie da się wyznaczyć R_3, E_2 — brakuje 1 danej. Wystarczy podać jedną z: U_R_3, U_J_1, U_E_2.
```

Częściowe wyniki są w `err.solution`. Bez `find` ten sam komunikat pojawia się jako ostrzeżenie.
Zawsze można też zapytać wprost: `sol.diagnose(["R_3"])`.

Solver najpierw **propaguje więzy**: szuka równania z jedną niewiadomą, wylicza ją
i zapisuje krok z nazwą prawa. Tak liczy się na kartce. Kiedy to nie wystarcza
(np. mostek), rozwiązuje pozostały **układ równań** naraz. Wykrywa też sytuacje brzegowe:

- `Contradiction`, gdy dane są sprzeczne,
- `Ambiguous`, gdy jest kilka rozwiązań (np. moc daje równanie kwadratowe),
- brak danych: ile danych brakuje i jakie pomiary by wystarczyły (rozwiązanie parametryczne + rząd gradientów).

Analiza AC: `c.solve(omega=...)` używa wskazów, bo C i L dostają impedancje 1/(jωC) i jωL.
Bez `omega` liczony jest stan ustalony DC.

```python
resistance(Resistor(10) + (Resistor(20) | Resistor(30)))      # 22
equivalent(supply(12) + Resistor(10) + shunt(Resistor(10)))   # E_th = 6 V, R_th = 5 Ω
blackbox(Resistor(10) | Resistor(10))                   # relacja na zaciskach
```

### Brakujący element: `Hole()`

```python
uklad = supply(12) + Resistor(10) + Hole() + ground
sol = uklad.solve(I_R_1=0.5)
sol["X_1"]           # X_1 → Resistor(14 Ω)
uklad.fill(sol)      # ... + Resistor(10 Ω) + Resistor(14 Ω) + ground
```

Dziura to nieznany dwójnik. Każdy liniowy dwójnik to `VoltageSource(E) + Resistor(Z)` (Thévenin),
więc dziura ma dwie niewiadome: E i Z ≥ 0. Jeden punkt pracy (jedno U i jedno I) nie wystarcza,
żeby je rozróżnić. Dlatego solver wybiera **najprostszy element, który pasuje do danych**:
najpierw rezystor (E = 0), potem źródło (Z = 0). Przyjęte założenie widać w `explain()`.
Z = 0 i E = 0 daje przewód. Rozwarcia (Z = ∞) ta postać nie wyraża.

### Obwód → kod: `code()`

```python
code(uklad)          # czysty kod electro, który buduje ten sam obwód
sch.to_code()        # to samo dla rysunku z electro-schematic
```

Układy szeregowo-równoległe wracają jako `+` / `|`. Obwód z jednym źródłem wraca jako `loop(...)`,
a kilka gałęzi ze źródłami jako gałęzie. Resztę (mostek, wzmacniacz) generator zapisuje jako `net(...)`.
Etykiety pisze tylko tam, gdzie automatyczna numeracja dałaby inne.

## Teoria, czyli co jest czym

Trzy warstwy połączone funktorami:

```
Circuit (drzewo składni)  ──netlist──►  Netlist (kospan)  ──semantyka──►  równania / relacje
   wolna kategoria                        Cospan(FinSet)                     LinRel (afiniczne)
   hipergrafowa                           dekorowany elementami
```

- **Obiekty** to liczby naturalne (liczba zacisków). **Morfizmy** to obwody.
- **Drzewo składni** (`Seq`, `Par`, `Tensor`, `Atom`, …) jest zachowane dokładnie tak, jak je zbudowano.
  Z niego rysuje się schemat.
- **Netlista** to kospan `lewe zaciski → węzły ← prawe zaciski`, udekorowany elementami.
  Złożenie `+` to wypchnięcie (pushout): sklejenie węzłów. Etykiety `node("A")` to kolimit po nazwach.
- **Węzeł** to pająk specjalnej przemiennej algebry Frobeniusa. `split`/`join` spełniają
  `split + join = wire` oraz prawo Frobeniusa. Fizycznie oznacza to I prawo Kirchhoffa
  (prądy się sumują) i jeden potencjał w węźle (potencjał się kopiuje).
- **Połączenie równoległe** jest wyprowadzone, a nie pierwotne: `f | g = split + (f @ g) + join`.
- **Semantyka**: każdy element to relacja między potencjałami i prądami na swoich zaciskach.
  Obwód to relacja (układ równań), a złożenie to złożenie relacji.
  `blackbox` eliminuje zmienne wewnętrzne. Dwa obwody są równoważne,
  gdy mają ten sam `blackbox`, i tak wyrażają się twierdzenia Thévenina i Nortona.
- **Masa** działa jak niejawny przewód w każdym morfizmie. Prąd może odpłynąć do masy,
  dlatego I prawa Kirchhoffa nie pisze się w węźle masy.

`tests/test_laws.py` sprawdza te prawa: łączność, prawo zamiany, naturalność `swap`,
prawa Frobeniusa, zygzak (yanking), sztylet, a także fizykę jako równania między obwodami
(`Resistor(x) + Resistor(y) ≅ Resistor(x+y)`, Norton ≅ Thévenin).

## Własne elementy

Element jest od razu obwodem (morfizmem). Wystarczy dziedziczyć po `TwoTerminal`
(albo po `Component`, gdy element ma więcej zacisków) i napisać jego prawa:

```python
import sympy as sp
from electro import NoValue, TwoTerminal

class Diode(NoValue, TwoTerminal):     # model ze stałym spadkiem napięcia
    prefix = "D"
    def law(self, U, I, x, ctx):
        return [(U - sp.Rational(7, 10), "dioda przewodząca: U = 0.7 V ({label})")]

(supply(5) + Resistor(430) + Diode() + ground).solve()
```

## Uruchomienie

Z katalogu głównego repo: `devenv shell`, potem `pytest`. Schematy i ślad w Markdown są w [`electro-render`](../electro-render).
