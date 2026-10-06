"""Kurs 3: biblioteka electro — obwody jako kod, rozwiązywanie, niewiadome i dziury, węzły, prąd zmienny,
twierdzenia, symulacja, schematy w kodzie, teoria pod spodem, analizy i zadania."""

from lib import Lesson, course

C = "3-biblioteka"


def intro():
    course(
        C,
        "Biblioteka electro",
        "Obwody zapisane w Pythonie: elementy łączone >> (szeregowo) i | (równolegle), zadanie z danymi "
        "i szukanymi, a solver rozwiązuje je krok po kroku — z niewiadomymi, literami i prądem zmiennym. Do "
        "tego twierdzenia Thévenina i superpozycji, symulacja w czasie z kodu, SPICE i trochę teorii "
        "kategorii, na której to wszystko stoi.",
    )


def lesson01():
    L = Lesson(C, "01-obwody-jako-kod", "1. Obwody jako kod")
    L.md("""
# Obwody jako kod

W każdej komórce z kodem jest już załadowana biblioteka `electro`. Najpierw tworzysz **elementy** —
każdy z nazwą:

```python
E = VoltageSource("E")
R_1 = Resistor("R_1")
```

Potem łączysz je w **obwód**. To sama budowa, bez żadnych liczb:

- `a >> b` — **szeregowo**: jeden za drugim,
- `a | b` — **równolegle**: obok siebie, między tymi samymi punktami,
- `~(a >> b >> c)` — **zamknięte**: koniec połączony z początkiem, pętla,
- `a @ b` — **obok siebie**, bez połączenia,
- `-a` — **odwrócony**,
- `Node("A")` — nazwany punkt, `GND` — masa.

Nic więcej: każdy obwód to te działania na elementach.

Liczby dochodzą dopiero w **zadaniu**: `Problem(obwód, {element: wartość})`. Zadanie pokazane w komórce
to jego schemat.
""")
    L.code("""
E, R_1, R_2, R_3 = VoltageSource("E"), Resistor("R_1"), Resistor("R_2"), Resistor("R_3")
uklad = Problem(~(E >> R_1 >> (R_2 | R_3)), {E: 12, R_1: 100, R_2: 200, R_3: 300})
uklad
""")
    L.md("""
Wartości można pisać tak jak na schemacie: `"4.7k"`, `"4k7"`, `"0,5"`, `"100n"`. Ten sam obwód da się
rozwiązać z różnymi danymi — budowa i liczby są osobno:
""")
    L.code("""
for r in [100, 1000]:
    sol = solve(Problem(~(E >> R_1 >> (R_2 | R_3)), {E: 12, R_1: r, R_2: 200, R_3: 300}))
    print(f"R_1 = {r} Ω: prąd ze źródła {sol(I(R_1))} A")
""")
    L.md("""
## Klocki

| zapis | co to |
|---|---|
| `Resistor`, `Capacitor`, `Inductor` | opornik, kondensator, cewka |
| `VoltageSource`, `CurrentSource` | źródło napięcia (+ na drugim końcu), źródło prądu (pcha od pierwszego do drugiego) |
| `Ammeter`, `Voltmeter` | idealne mierniki; ich odczyt to dana `I(A_1)` albo `U(V_1)` |
| `GND >> a >> b >> GND` | od masy do masy: zamknięty obwód |
| `Node("A")` | nazwany punkt; ten sam obiekt w dwóch miejscach to jeden punkt |
| `~(a >> b >> c)` | pętla |
| `-a` | ten sam element odwrócony (źródło — zmiana biegunowości) |
| `a >> e >> b` | element między punktami `a` i `b` |
| `T >> (b @ c @ e)` | element o więcej niż dwóch zaciskach: punkt na każdy |
| `a @ b` | kawałki obok siebie |

Drabinka: każdy szczebel to opornik od linii do masy. Punkty `A` i `B` są nazwane, więc łatwo zapisać,
co gdzie dochodzi:
""")
    L.code("""
E, A, B = VoltageSource("E"), Node("A"), Node("B")
R = [Resistor(f"R_{k}") for k in range(1, 6)]
drabinka = Problem(
    ((GND >> E >> R[0] >> A >> R[1] >> GND) @ (A >> R[2] >> B >> R[3] >> GND) @ (B >> R[4] >> GND)),
    {E: 10, R[0]: 1, R[1]: 2, R[2]: 1, R[3]: 2, R[4]: 2},
)
print("prąd ze źródła:", solve(drabinka)(I(R[0])), "A")
drabinka
""")
    L.md("""
## Ze schematu do kodu i z powrotem

Każdy schemat w notatce jest w kodzie zmienną o swojej nazwie (np. `uklad1`) — zadaniem, na którym działa
wszystko z tej lekcji. A każdy obwód z kodu można **narysować jako schemat do edycji**: w komórce Schemat
otwórz kartę **Kod**, wklej kod i wróć do rysunku.
""")
    L.save()


def lesson02():
    L = Lesson(C, "02-rozwiazywanie", "2. Rozwiązywanie")
    L.md("""
# Rozwiązywanie

`solve(zadanie)` zwraca **rozwiązanie**. Pytasz je o wielkości:

- `sol(I(R_1))`, `sol(U(R_1))`, `sol(P(R_1))` — prąd, napięcie, moc elementu,
- `sol(V(A))` — potencjał punktu, `sol(U(A, B))` — napięcie między dwoma,
- `sol(Parameter(R_1))` — wartość elementu,
- `sol("I_R_1")`, `sol("U_E / I_E")` — to samo po nazwach, także wyrażenia.

Liczby są dokładne (`sympy`): $\\frac{1}{3}$ zostaje ułamkiem, a nie 0,333….
""")
    L.code("""
E, R_1, R_2, wy = VoltageSource("E"), Resistor("R_1"), Resistor("R_2"), Node("wy")
dzielnik = Problem(GND >> E >> R_1 >> wy >> R_2 >> GND, {E: 12, R_1: 1000, R_2: 2000})
sol = solve(dzielnik)
print("V_wy =", sol(V(wy)), "V")
print("moc R_2:", sol(P(R_2)), "W  ≈", float(sol(P(R_2))), "W")
""")
    L.md("""
## Dane i szukane

Element bez wartości to niewiadoma. Danymi mogą być też **wielkości**: `I(R_1): "0,5"` znaczy, że przez
$R_1$ płynie 0,5 A. Trzeci argument `Problem` to lista **szukanych** — wtedy `sol.answers` daje odpowiedzi,
a `steps(sol)` pokazuje rozwiązanie krok po kroku, każdy krok z uzasadnieniem.
""")
    L.code("""
E, R_1, R_2, R_3, R_4, A_1 = (VoltageSource("E"), Resistor("R_1"), Resistor("R_2"), Resistor("R_3"),
                              Resistor("R_4"), Ammeter("A_1"))
zadanie = Problem(
    ~(E >> R_1 >> ((R_2 >> A_1) | (R_3 >> R_4))),
    {R_1: 3, R_2: 18, R_3: 3, R_4: 6, I(A_1): 2},
    [Parameter(E)],
)
sol = solve(zadanie)
sol(Parameter(E))
""")
    L.code("""
steps(sol)
""")
    L.md("""
Danych może nie być wcale — litery też są wartościami. Wtedy wynik to wzór:
""")
    L.code("""
E, R_1, R_2 = VoltageSource("E"), Resistor("R_1"), Resistor("R_2")
solve(Problem(~(E >> R_1 >> R_2), {E: "E", R_1: "R_1", R_2: "R_2"}))(U(R_2))
""")
    L.md("""
## Jak to działa

Każdy element to **prawo** (opornik: $U = R \\cdot I$), a punkty dokładają prawa Kirchhoffa. Solver szuka
równania z jedną niewiadomą, wylicza ją i zapisuje krok — jak na kartce. Gdy to nie wystarcza (np.
w mostku), rozwiązuje pozostałe równania naraz. Napięcie elementu to spadek od jego pierwszego końca do
drugiego — także źródła: źródło 12 V ma $U = -12$ V, bo napięcie na nim rośnie.
""")
    L.save()


def lesson03():
    L = Lesson(C, "03-niewiadome-i-dziury", "3. Niewiadome i dziury")
    L.md("""
# Niewiadome i dziury

Wartość, której nie znasz, zostawiasz bez danej. Solver szuka jej z innych danych — każda niewiadoma
potrzebuje jednej **niezależnej** danej.

## Nieznany opór z pomiaru
""")
    L.code("""
E, R_1, R_2 = VoltageSource("E"), Resistor("R_1"), Resistor("R_2")
dzielnik = Problem(~(E >> R_1 >> R_2), {E: 12, R_1: 100, U(R_2): 4}, [Parameter(R_2)])
steps(solve(dzielnik))
""")
    L.md("""
## Minus w wyniku

Dwa źródła w jednej pętli; prąd 2 A przez 4 Ω daje 8 V, a pierwsze źródło ma 12 V. Ujemny wynik znaczy,
że drugie źródło jest naprawdę skierowane odwrotnie niż w zapisie:
""")
    L.code("""
E_1, R, E_2 = VoltageSource("E_1"), Resistor("R"), VoltageSource("E_2")
solve(Problem(~(E_1 >> R >> E_2), {E_1: 12, R: 4, I(R): 2}))(Parameter(E_2))
""")
    L.md("""
## Za mało danych

Solver nie zgaduje — mówi, ilu danych brakuje i które by wystarczyły:
""")
    L.code("""
E, R_1, R_2 = VoltageSource("E"), Resistor("R_1"), Resistor("R_2")
try:
    solve(Problem(~(E >> R_1 >> R_2), {E: 12, R_1: 100}, [Parameter(R_2)])).answers
except MissingData as e:
    display(e)
""")
    L.md("""
## Sprzeczne dane

Gdy danych jest za dużo i nie pasują do siebie, solver wskazuje te, które się wykluczają:
""")
    L.code("""
try:
    solve(Problem(~(E >> R_1 >> R_2), {E: 12, R_1: 10, R_2: 20, I(R_1): 1}))
except Contradiction as e:
    display(e)
""")
    L.md("""
## Dwa rozwiązania

Moc to $P = U \\cdot I$ — równanie kwadratowe. Oporniki 2 Ω i 8 Ω dają w tej pętli tę samą moc 8 W;
jedna dana więcej rozstrzyga:
""")
    L.code("""
try:
    solve(Problem(~(E >> R_1 >> R_2), {E: 12, R_2: 4, P(R_1): 8}, [Parameter(R_1)])).answers
except Ambiguous as e:
    display(e)
""")
    L.md("""
# Dziury: `Hole`

Dziura to element, o którym nie wiemy nawet, **czym** jest. Każdy liniowy dwójnik to źródło z oporem,
ale z jednego pomiaru nie da się ich rozdzielić — więc `fill` wstawia **najprostszy** pasujący element:
przewód, przerwę, rezystor, a dopiero potem źródło.

Żarówka 12 Ω ma dostać 0,5 A z akumulatora 12 V (tyle pokazuje amperomierz). Co wstawić? Uruchom schemat
przyciskiem ▶ — albo policz to kodem: schemat to zmienna `zarowka`.
""")
    L.circuit(
        "zarowka",
        """E_1 = VoltageSource("E_1")
R_1 = Resistor("R_1")
A_1 = Ammeter("A_1")
X_1 = Hole("X_1")
zarowka = Problem(~(E_1 >> R_1 >> A_1 >> X_1), {E_1: 12, R_1: 12, I(A_1): "0,5"})""",
        solve=True,
    )
    L.code("""
f = fill(zarowka, zarowka["X_1"])
print("w dziurze:", f.by.kind.name, "=", f.solution(Parameter(f.by)))
""")
    L.md("""
Prąd płynący „pod prąd” akumulatora (−1 A) zrobi tylko źródło — ładowarka:
""")
    L.code("""
E, R, X = VoltageSource("E"), Resistor("R"), Hole("X")
f = fill(Problem(~(E >> R >> X), {E: 12, R: 2, I(R): -1}), X)
print(f.by.kind.name, f.solution(Parameter(f.by)))
""")
    L.md("""
## Pomiar na schemacie: amperomierz z odczytem

Znany prąd to **amperomierz z odczytem**: dana pomiarowa, a nie źródło prądu (źródło prądu wymusza prąd,
ale jego napięcie byłoby kolejną niewiadomą). W edytorze odczyt wpisujesz w polu **Odczyt** amperomierza.
""")
    L.circuit(
        "zadanie4",
        """E = VoltageSource("E")
R_1 = Resistor("R_1")
R_2 = Resistor("R_2")
A_1 = Ammeter("A_1")
R_3 = Resistor("R_3")
R_4 = Resistor("R_4")
zadanie4 = Problem(~(E >> R_1 >> ((R_2 >> A_1) | (R_3 >> R_4))), {R_1: 3, R_2: 18, I(A_1): 2, R_3: 3, R_4: 6})""",
        solve=True,
    )
    L.save()


def lesson04():
    L = Lesson(C, "04-wezly", "4. Węzły i netlisty")
    L.md("""
# Węzły

Nie każdy obwód jest szeregowo-równoległy — mostek Wheatstone'a albo trójkąt oporników nie są ani jednym,
ani drugim. Wtedy łączysz przez **nazwane punkty**: ten sam `Node` w kilku miejscach to jeden punkt.
`a >> element >> b` stawia element między punktami, a `@` zbiera kawałki obok siebie — tak jak netlista
w SPICE.
""")
    L.code("""
A, B, C = Node("A"), Node("B"), Node("C")
E, R = VoltageSource("E"), [Resistor(f"R_{k}") for k in range(1, 6)]
mostek = Problem(
    ((GND >> E >> A) @ (A >> R[0] >> B) @ (B >> R[1] >> GND) @ (A >> R[2] >> C) @ (C >> R[3] >> GND) @ (B >> R[4] >> C)),
    {E: 10, R[0]: 100, R[1]: 200, R[2]: 150, R[3]: 150, R[4]: 50},
)
sol = solve(mostek)
print("U_BC =", sol(U(B, C)), "V,  prąd przez mostek:", sol(I(R[4])), "A")
""")
    L.md("""
Element o więcej niż dwóch zaciskach ma wszystkie końce po prawej: `OA >> (plus @ minus @ wy)` — punkt
na każdy zacisk. Idealny wzmacniacz operacyjny `OpAmp` ma wejście nieodwracające, odwracające i wyjście. Tu wzmacniacz odwracający
o wzmocnieniu $-\\frac{R_2}{R_1} = -10$:
""")
    L.code("""
we, minus, wy = Node("we"), Node("minus"), Node("wy")
E, R_1, R_2, R_L, OA = VoltageSource("E"), Resistor("R_1"), Resistor("R_2"), Resistor("R_L"), OpAmp("OA")
wzmacniacz = Problem(
    ((GND >> E >> we) @ (we >> R_1 >> minus) @ (minus >> R_2 >> wy) @ (OA >> (GND @ minus @ wy)) @ (wy >> R_L >> GND)),
    {E: "0,5", R_1: 1000, R_2: 10000, R_L: 2000},
)
print("U_wy =", solve(wzmacniacz)(V(wy)), "V")
""")
    L.md("""
## Netlista

Każdy obwód ma swoją **netlistę**: elementy i punkty (numerowane), do których dochodzą ich zaciski:
""")
    L.code("""
for element, punkty in netlist(mostek.circuit).parts:
    print(element.name, punkty)
""")
    L.save()


def lesson05():
    L = Lesson(C, "05-prad-zmienny", "5. Prąd zmienny")
    L.md("""
# Prąd zmienny: wskazy

Przy napięciu sinusoidalnym kondensator i cewka zachowują się jak „opory” zależne od częstotliwości —
**impedancje**:

$$Z_C = \\frac{1}{j\\omega C} \\qquad Z_L = j\\omega L \\qquad \\omega = 2\\pi f$$

Zadanie ze źródłem sinusoidalnym (`SineSource`: amplituda, częstotliwość `f` i faza `phase` w stopniach)
liczy się samo metodą **wskazów** — liczb zespolonych: moduł to amplituda, a argument to przesunięcie fazy.
""")
    L.code("""
import cmath, math
S, R, C, wy = SineSource("S"), Resistor("R"), Capacitor("C"), Node("wy")
rc = Problem(GND >> S >> R >> wy >> C >> GND, {S: {"": 10, "f": 50}, R: 1000, C: "3.3u"})
u = complex(solve(rc)(V(wy)))
print(f"amplituda {abs(u):.2f} V, faza {math.degrees(cmath.phase(u)):.1f}°")
""")
    L.md("""
## Charakterystyka filtru

Częstotliwość można też podać wprost: `solve(zadanie, AC(ω))` liczy wskazy przy $\\omega$, a zwykłe
źródło napięcia jest wtedy wskazem o swojej wartości. Filtr RC przepuszcza niskie częstotliwości, a tłumi
wysokie; częstotliwość graniczna $f_g = \\frac{1}{2\\pi RC} \\approx 48$ Hz — tam zostaje
$\\frac{1}{\\sqrt 2} \\approx 71\\%$ amplitudy:
""")
    L.code("""
E = VoltageSource("E")
filtr = Problem(GND >> E >> R >> wy >> C >> GND, {E: 10, R: 1000, C: "3.3u"})
for f in [5, 20, 48, 100, 500, 2000]:
    u = abs(complex(solve(filtr, AC(2 * math.pi * f))(V(wy))))
    print(f"{f:>5} Hz: {u / 10 * 100:5.1f}% ", "█" * round(u * 4))
""")
    L.md("""
## Rezonans

Cewka i kondensator razem mają częstotliwość, przy której ich impedancje się znoszą:
$f_0 = \\frac{1}{2\\pi\\sqrt{LC}}$. W obwodzie szeregowym RLC prąd jest wtedy największy:
""")
    L.code("""
E, R, L_, C_ = VoltageSource("E"), Resistor("R"), Inductor("L"), Capacitor("C")
rlc = Problem(~(E >> R >> L_ >> C_), {E: 1, R: 10, L_: 0.01, C_: 1e-6})
f0 = 1 / (2 * math.pi * math.sqrt(0.01 * 1e-6))
print(f"f0 = {f0:.0f} Hz")
for f in [0.5 * f0, 0.9 * f0, f0, 1.1 * f0, 2 * f0]:
    i = abs(complex(solve(rlc, AC(2 * math.pi * f))(I(R))))
    print(f"{f:7.0f} Hz: I = {i * 1000:6.2f} mA")
""")
    L.save()


def lesson06():
    L = Lesson(C, "06-twierdzenia", "6. Komponenty i twierdzenia")
    L.md("""
# Każdy obwód jest komponentem

Złożenie dwóch kawałków to znowu kawałek: `R_1 >> R_2` ma dwa końce i jedno prawo między nimi. `>>` skleja
końce i **wyrzuca to, co jest w środku** — zostaje tylko związek napięcia $U$ z prądem $I$ na brzegu.
`.component` go pokazuje. Opór szeregowy czy równoległy nie jest tu żadną regułą: wychodzi z praw elementów.
""")
    L.code("""
R_1, R_2, R_3, E = Resistor("R_1"), Resistor("R_2"), Resistor("R_3"), VoltageSource("E")
print("szeregowo: ", (R_1 >> R_2).component)
print("równolegle:", (R_1 | R_2).component)
print("z źródłem: ", (E >> R_1 >> (R_2 | R_3)).component)
print("z kondensatorem:", (R_1 >> Capacitor("C")).component)
""")
    L.md("""
Dwa kawałki są równoważne dokładnie wtedy, gdy mają to samo prawo na końcach.

## Thévenin

Każdy liniowy obwód widziany z dwóch punktów to jedno źródło $E_{th}$ z jednym oporem $R_{th}$: $E_{th}$ to
napięcie, gdy nic nie jest podłączone, a $R_{th}$ — o ile napięcie spada na każdy amper pobrany.
`resistance(zadanie, A, B)` liczy $R_{th}$ (wpuszcza prąd i patrzy, jak rośnie napięcie):
""")
    L.code("""
A = Node("A")
dzielnik = Problem(GND >> E >> R_1 >> A >> R_2 >> GND, {E: 12, R_1: 10, R_2: 10})
print("E_th =", solve(dzielnik)(V(A)), "V,  R_th =", resistance(dzielnik, A, GND), "Ω")
""")
    L.md("""
Dzielnik 12 V z dwóch oporników 10 Ω to dla obciążenia po prostu 6 V przez 5 Ω.

## Superpozycja

W obwodzie liniowym każde źródło działa niezależnie: wynik to suma tego, co daje każde źródło samo
(pozostałe wyłączone, czyli z wartością 0):
""")
    L.code("""
J = CurrentSource("J")
obwod = ((GND >> E >> R_1 >> A) @ (A >> R_2 >> GND) @ (GND >> J >> A))
dane = {E: 12, R_1: 10, R_2: 10, J: 1}
samo_E = solve(Problem(obwod, {**dane, J: 0}))(U(R_2))
samo_J = solve(Problem(obwod, {**dane, E: 0}))(U(R_2))
print("samo E:", samo_E, "V,  samo J:", samo_J, "V,  razem:", samo_E + samo_J, "=", solve(Problem(obwod, dane))(U(R_2)), "V")
""")
    L.save()


def lesson07():
    L = Lesson(C, "07-symulacja-z-kodu", "7. Symulacja w czasie z kodu")
    L.md("""
# `simulate()`

Obwody z diodami, tranzystorami i układami scalonymi liczy się w czasie. `simulate(zadanie, until=...)`
liczy przebiegi od chwili włączenia (kondensatory puste) do `until` sekund i zwraca **ślad**:

- `slad(V(A))`, `slad("I_R_1")` — cały przebieg jednej wielkości,
- `slad.at("V_A", 0.5)` — wartość w chwili 0,5 s,
- `plot(slad, "V_A", "I_R_1")` — wykres.

Elementy „tylko w czasie” to m.in. `Diode`, `LED`, `Zener`, `NPN`, `PNP`, `NMOS`, `PMOS`, `Timer555`,
`Lamp`, `Motor`, `Relay`, bramki `AND`, `OR`, `NOT`, `XOR`, `NAND`, `NOR` i źródła `SineSource`,
`SquareSource`.
""")
    L.code("""
S, D, C, R = SineSource("S"), Diode("D"), Capacitor("C"), Resistor("R")
we, wy = Node("we"), Node("wy")
prostownik = Problem(
    ((GND >> S >> we) @ (we >> D >> wy) @ (wy >> C >> GND) @ (wy >> R >> GND)),
    {S: {"": 10, "f": 50}, C: "220u", R: 1000},
)
slad = simulate(prostownik, until=0.1)
koniec = slad(V(wy))[-400:]
print("tętnienia:", round(max(koniec) - min(koniec), 2), "V")
plot(slad, "V_we", "V_wy")
""")
    L.md("""
## Wejścia

Łączniki, przyciski, potencjometry i czujniki mają **wejścia**, które podajesz w `inputs`: liczbą albo
funkcją czasu. Nazwy: `S_1_closed` (0/1), `P_1_position` (0–1), `LDR_1_lux`, `RT_1_temperature`. Tu
łącznik zamyka się po 10 ms, a silnik rusza:
""")
    L.code("""
E, S_1, M_1 = VoltageSource("E"), Switch("S_1"), Motor("M_1")
naped = Problem(~(E >> S_1 >> M_1), {E: 6})
slad = simulate(naped, until=0.3, inputs={"S_1_closed": lambda t: 1 if t > 0.01 else 0})
print(f"prąd po 0,3 s: {slad.at('I_M_1', 0.3) * 1000:.0f} mA")
plot(slad, "I_M_1")
""")
    L.md("""
## Bramki logiczne

Bramki pracują przy 5 V względem masy. Pierścień z trzech negacji i kondensatorów to **generator**: każda
bramka odwraca sygnał poprzedniej, a kondensatory opóźniają zmiany — więc stan nigdy się nie ustala.
""")
    L.code("""
from functools import reduce
from operator import matmul

a, b, c = Node("a"), Node("b"), Node("c")
kawalki, dane = [], {}
for k, (z, do) in enumerate([(a, b), (b, c), (c, a)], 1):
    n, r, cap, srodek = NOT(f"N_{k}"), Resistor(f"R_{k}"), Capacitor(f"C_{k}"), Node()
    kawalki += [n >> (z @ srodek), srodek >> r >> do, do >> cap >> GND]
    dane |= {r: 1000, cap: "1u"}
pierscien = Problem(reduce(matmul, kawalki), dane)
plot(simulate(pierscien, until=0.02), "V_a")
""")
    L.save()


def lesson08():
    L = Lesson(C, "08-schematy-w-kodzie", "8. Schematy w kodzie")
    L.md("""
# Schematy w kodzie

Każdy schemat z notatki jest w kodzie zmienną o swojej nazwie — zadaniem (`Problem`) z tym, co na
rysunku: wartościami, odczytami mierników, strzałkami z danymi i szukanymi. Nazwa ze spacjami i polskimi
znakami zamienia się w zmienną bez nich: „Układ 1” to `układ1`. Można też sięgnąć po schemat po nazwie:
`schemat("Układ 1")`. Jego elementy mają nazwy z rysunku: `uklad1["R_1"]` to opornik, a `sol("I_R_1")` jego
prąd.

`schematic(zadanie, sol)` rysuje obwód z wynikami przy elementach — do sprawozdania:
""")
    L.code("""
E, R_1, R_2, R_3 = VoltageSource("E"), Resistor("R_1"), Resistor("R_2"), Resistor("R_3")
zadanie = Problem(~(E >> R_1 >> (R_2 | R_3)), {E: 12, R_1: 4, R_2: 2, R_3: 3})
schematic(zadanie, solve(zadanie))
""")
    L.md("""
## Widok kodu

Karta **Kod** w komórce schematu pokazuje rysunek jako kod — taki jak w tych lekcjach — a po zmianie kodu
rysuje go z powrotem. Gdy zmieniasz tylko wartości, rysunek zostaje, jaki był.
""")
    L.save()


def lesson09():
    L = Lesson(C, "09-teoria", "9. Teoria: obwody jako kategoria")
    L.md("""
# Co jest pod spodem

Ta lekcja jest dla ciekawych — nie trzeba jej znać, żeby korzystać z biblioteki. `electro` traktuje obwody
jako **morfizmy kategorii hipergrafowej**. Brzmi groźnie, ale znaczy coś prostego: obwód to „pudełko
z końcami po lewej i prawej”, a jedyne, co z pudełkami robimy, to składanie.

- **Obiekty** to liczby naturalne — ile końców. **Morfizmy** to obwody: $m \\to n$. Opornik to $1 \\to 1$.
- `f >> g` to **złożenie** (szeregowo): prawe końce `f` sklejone z lewymi `g`.
- `f @ g` to **iloczyn monoidalny**: obok siebie, bez połączenia.
- **Punkt** to *pająk* algebry Frobeniusa: `wire` ($1 \\to 1$), `cap` ($0 \\to 2$), `cup` ($2 \\to 0$)
  i każdy inny z dowolną liczbą końców. Że pająki się sklejają, to fizycznie I prawo Kirchhoffa (prądy się
  sumują) i jeden potencjał w punkcie.
- **Pętla** nie jest osobnym klockiem: `~(a >> b)` to `cap >> ((a >> b) @ wire) >> cup`, a `-f`
  to `f` zgięty przez `cap` i `cup` — transpozycja.
""")
    L.code("""
R_1, R_2 = Resistor("R_1"), Resistor("R_2")
petla = cap >> ((R_1 >> R_2) @ wire) >> cup
print(netlist(petla).parts)
print(netlist(~(R_1 >> R_2)).parts)
""")
    L.md("""
## Semantyka

Każdy element to **relacja** między potencjałami i prądami na końcach (opornik: $U = RI$), a obwód złożony
z elementów — relacja złożona z relacji. `>>` eliminuje zmienne wewnętrzne i zostawia relację na brzegu
(`.component`): dwa obwody są równoważne, gdy mają tę samą. Złożenie w kategorii obwodów przechodzi
na złożenie relacji — dlatego solver może pracować na dowolnie złożonych kawałkach i zawsze dostanie ten
sam wynik, jakby liczył całość.

**Netlista** to kospan: końce lewe → punkty ← końce prawe. Złożenie `>>` to wypchnięcie (*pushout*):
sklejenie punktów. Schemat narysowany na siatce jest jeszcze jedną składnią tego samego — dwa zaciski
w tym samym punkcie siatki to jeden punkt, dokładnie jak ten sam `Node` w dwóch miejscach kodu.

Po więcej: John Baez i Brendan Fong, *A Compositional Framework for Passive Linear Networks* (2015).
""")
    L.save()


def lesson10():
    L = Lesson(C, "10-analizy-i-zadania", "10. Analizy i zadania")
    L.md("""
# Analizy i zadania

Poza rozwiązaniem jednego układu `electro` robi analizy, które liczą ten sam układ setki razy — szybko, bo
układ jest rozwiązany raz, z literą w miejscu tego, co się zmienia, a potem tylko podstawiane są liczby.

## Charakterystyka częstotliwościowa

`bode(zadanie)` rysuje wzmocnienie w dB i fazę od 10 Hz do 1 MHz, z zaznaczoną częstotliwością graniczną
$f_g$ (−3 dB) — dla nazwanych punktów, względem źródła. Na schemacie to samo robi przycisk ∿.
""")
    L.code("""
E, R, C, wy = VoltageSource("E"), Resistor("R"), Capacitor("C"), Node("wy")
filtr = Problem(GND >> E >> R >> wy >> C >> GND, {E: 1, R: "1k", C: "1u"})
bode(filtr)
""")
    L.circuit(
        "filtr_rc",
        """E_1 = VoltageSource("E_1")
R_1 = Resistor("R_1")
C_1 = Capacitor("C_1")
filtr_rc = Problem(GND >> E_1 >> R_1 >> Node("wy") >> C_1 >> GND, {E_1: 1, R_1: "1k", C_1: "1u"})""",
    )
    L.md("""
## Zmiana wartości elementu

`swept(zadanie, element, wartości, [wielkości])` pokazuje, jak wynik zależy od wartości jednego elementu:
""")
    L.code("""
E, R_1, R_2, A = VoltageSource("E"), Resistor("R_1"), Resistor("R_2"), Node("A")
dzielnik = Problem(GND >> E >> R_1 >> A >> R_2 >> GND, {E: 12, R_1: "1k", R_2: "1k"})
wartosci = [100, 1000, 10000]
for r, u in zip(wartosci, swept(dzielnik, R_2, wartosci, [V(A)])[V(A)]):
    print(f"R_2 = {int(r):>5} Ω: V_A = {float(u):.2f} V")
""")
    L.md("""
## Tolerancje

Prawdziwe oporniki mają tolerancję (np. ±5 %). `spread` buduje układ 500 razy z losowymi wartościami
w tych granicach i pokazuje, jak bardzo rozrzuca się wynik:
""")
    L.code("""
spread(dzielnik, "V_A", tol=0.05)
""")
    L.md("""
## Zadania do sprawdzenia

`task(zadanie, "I_R_1", "treść")` pokazuje treść i pole na odpowiedź. Odpowiedź jest sprawdzana w
przeglądarce z dokładnością 1 %, a w notatce zapisany jest tylko jej skrót — nie widać jej ani na stronie,
ani w pliku. Wpisz wynik (np. `0,4` albo `400 mA`) i kliknij **Sprawdź**.
""")
    L.code("""
E, R_1, R_2 = VoltageSource("E"), Resistor("R_1"), Resistor("R_2")
task(Problem(~(E >> R_1 >> R_2), {E: 12, R_1: 10, R_2: 20}), "I_R_1", "Jaki prąd płynie przez oba oporniki?")
""")
    L.save()


if __name__ == "__main__":
    intro()
    for lesson in (lesson01, lesson02, lesson03, lesson04, lesson05, lesson06, lesson07, lesson08, lesson09, lesson10):
        lesson()
