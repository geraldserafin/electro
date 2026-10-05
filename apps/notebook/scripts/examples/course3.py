"""Kurs 3: biblioteka electro — obwody jako kod, rozwiązywanie, netlisty, prąd zmienny, twierdzenia,
symulacja, schematy w kodzie i teoria pod spodem. (Lekcja 3, niewiadome i dziury: make_examples.py.)"""

from electro import Capacitor, Resistor, ground, node, supply
from lib import Lesson, course

C = "3-biblioteka"


def intro():
    course(
        C,
        "Biblioteka electro",
        "Obwody zapisane w Pythonie: szeregowo to +, równolegle to |, a solver rozwiązuje je krok po kroku, "
        "z niewiadomymi, literami i prądem zmiennym. Do tego netlisty, twierdzenia Thévenina i Nortona, "
        "symulacja w czasie z kodu i trochę teorii kategorii, na której to wszystko stoi.",
    )


def lesson01():
    L = Lesson(C, "01-obwody-jako-kod", "1. Obwody jako kod")
    L.md("""
# Obwody jako kod

W każdej komórce z kodem jest już załadowana biblioteka `electro`. Obwód buduje się z **klocków**
(elementów) i dwóch działań:

- `a + b` — **szeregowo**: jeden za drugim,
- `a | b` — **równolegle**: obok siebie, między tymi samymi węzłami.

Każdy klocek ma zaciski z lewej i z prawej. Opornik to „1 → 1”: jeden zacisk wchodzi, jeden wychodzi.
`supply(12)` to źródło 12 V wychodzące z masy (0 → 1), a `ground` wraca do masy (1 → 0). Cały obwód
od masy do masy jest zamknięty (0 → 0).
""")
    L.code("""
uklad = supply(12) + Resistor(100) + (Resistor(200) | Resistor(300)) + ground
uklad
""")
    L.md("""
Wartości można pisać tak jak na schemacie: `"4.7k"`, `"4k7"`, `"0,5"`, `"100n"`. Każdy element dostaje
nazwę sam (`R_1`, `R_2`, …), w kolejności wpisania; własną nadaje `label=`.

`schematic()` rysuje obwód z kodu, a `code()` robi odwrotnie — z każdego obwodu (także
narysowanego) pisze kod, który go buduje:
""")
    L.code("""
schematic(uklad)
""")
    L.code("""
print(code(uklad))
""")
    L.md("""
## Klocki

| zapis | co to |
|---|---|
| `Resistor(10)`, `Capacitor("1u")`, `Inductor("2m")` | opornik, kondensator, cewka |
| `VoltageSource(12)`, `CurrentSource("0,5")` | źródło napięcia (+ z prawej), źródło prądu (pcha w prawo) |
| `Ammeter()`, `Voltmeter()` | idealne mierniki; argument to odczyt z zadania |
| `supply(v)`, `ground` | źródło od masy; powrót do masy |
| `shunt(x)` | element od linii do masy (linia biegnie dalej) |
| `loop(a, b, c)` | zamknięta pętla z elementów po kolei |
| `x.transpose()` | ten sam element odwrócony (źródło — zmiana biegunowości) |
| `node("A")` | nazwany punkt: potem `sol.V("A")` |

`loop` jest najwygodniejszy do zadań z jedną pętlą, a `shunt` do „drabinek”:
""")
    L.code("""
drabinka = supply(10) + Resistor(1) + shunt(Resistor(2)) + Resistor(1) + shunt(Resistor(2)) + Resistor(2) + ground
print("prąd ze źródła:", drabinka.solve()["R_1"].I, "A")
schematic(drabinka)
""")
    L.md("""
## Ze schematu do kodu i z powrotem

Każdy schemat w notatce jest w kodzie zmienną o swojej nazwie (np. `uklad1`) — obiektem, na którym
działa wszystko z tej lekcji: `.solve()`, `code()`, `schematic()`. A każdy obwód z kodu można
**narysować jako schemat do edycji**: dodaj komórkę Schemat, otwórz jej kartę **Kod**, wklej kod
i wróć do rysunku.
""")
    L.save()


def lesson02():
    L = Lesson(C, "02-rozwiazywanie", "2. Rozwiązywanie")
    L.md("""
# Rozwiązywanie

`obwod.solve()` rozwiązuje obwód i zwraca **rozwiązanie**. Z niego odczytujesz wszystko, czego
potrzebujesz:

- `sol["R_1"]` — element: jego wartość, napięcie `U`, prąd `I`, moc `P`,
- `sol["R_1"].I`, `.U`, `.P` — pojedyncze wielkości (dokładne: ułamki, pierwiastki),
- `sol.V("A")` — potencjał nazwanego węzła, `sol.U("A", "B")` — napięcie między dwoma.
""")
    L.code("""
dzielnik = supply(12) + Resistor(1000) + node("wy") + shunt(Resistor(2000))
sol = dzielnik.solve()
print(sol["R_1"])
print("V_wy =", sol.V("wy"), "V")
print("moc R_2:", sol["R_2"].P, "W  ≈", float(sol["R_2"].P), "W")
""")
    L.md("""
## Dane i niewiadome

Element bez wartości (`Resistor()`) to niewiadoma. Dane z zadania podaje się jako argumenty: nazwa
wielkości to litera i nazwa elementu — `I_R_1` (prąd), `U_R_2` (napięcie), `P_R_1` (moc). `find=` mówi,
czego szukasz — wtedy wynik to odpowiedź, a `steps()` pokazuje tylko potrzebne kroki.
""")
    L.code("""
zadanie = loop(VoltageSource(label="E"), Resistor(3), (Resistor(18) + Ammeter(2)) | (Resistor(3) + Resistor(6)))
sol = zadanie.solve(find="E")
sol
""")
    L.code("""
steps(sol)
""")
    L.md("""
Dane mogą też być dowolnym równaniem — `Eq(...)` z wielkości `U("R_1")`, `I("R_1")`, `P("R_1")`,
`V("A")`. Tu wiemy tylko, że na $R_1$ jest dwa razy większe napięcie niż na $R_2$:
""")
    L.code("""
dwa = supply(9) + Resistor(300) + Resistor() + ground
dwa.solve(Eq(U("R_1"), 2 * U("R_2")), find="R_2")
""")
    L.md("""
## Jak to działa

Solver najpierw **propaguje**: szuka równania z jedną niewiadomą (prawo Ohma, prawa Kirchhoffa, prawo
źródła…), wylicza ją i zapisuje krok — dokładnie jak na kartce. Gdy to nie wystarcza (np. w mostku),
rozwiązuje pozostały układ równań naraz. Wszystkie liczby są dokładne (`sympy`): $\\frac{1}{3}$ zostaje
ułamkiem, a nie 0,333….
""")
    L.save()


def lesson04():
    L = Lesson(C, "04-netlisty", "4. Netlisty: net() i node()")
    L.md("""
# Netlisty

Nie każdy obwód da się zapisać przez `+` i `|` — mostek Wheatstone'a albo trójkąt oporników nie są ani
szeregowe, ani równoległe (i dlatego `schematic()` nie umie ich sam ułożyć — narysuj je na schemacie).
Na to jest `net(...)`: lista elementów, każdy z nazwami węzłów, do których
dochodzą jego zaciski — tak jak w SPICE. Węzeł `"0"` albo `"GND"` to masa.
""")
    L.code("""
mostek = net(
    (VoltageSource(10), "GND", "A"),
    (Resistor(100), "A", "B"), (Resistor(200), "B", "GND"),
    (Resistor(150), "A", "C"), (Resistor(150), "C", "GND"),
    (Resistor(50), "B", "C"),
)
sol = mostek.solve()
print("U_BC =", sol.U("B", "C"), "V,  prąd przez mostek:", sol["R_5"].I, "A")
""")
    L.md("""
Elementy o więcej niż dwóch zaciskach podaje się tak samo — węzeł na każdy zacisk. Wzmacniacz
operacyjny (`OpAmp`) ma trzy: wejście nieodwracające, odwracające i wyjście. Tu wzmacniacz odwracający
o wzmocnieniu $-\\frac{R_2}{R_1} = -10$:
""")
    L.code("""
wzmacniacz = net(
    (VoltageSource("0,5"), "GND", "we"),
    (Resistor(1000), "we", "minus"),
    (Resistor(10000), "minus", "wy"),
    (OpAmp(), "GND", "minus", "wy"),
    (Resistor(2000), "wy", "GND"),
)
print("U_wy =", wzmacniacz.solve().V("wy"), "V")
""")
    L.md("""
## `node()` w zapisie z `+`

W zapisie szeregowym `node("A")` nazywa punkt, żeby potem odczytać jego potencjał. Dwa punkty o tej
samej nazwie są jednym węzłem — także wtedy, gdy leżą w różnych częściach wyrażenia:
""")
    L.code("""
z_nazwami = supply(12) + Resistor(10) + node("A") + shunt(Resistor(20)) + Resistor(5) + node("B") + shunt(Resistor(15))
sol = z_nazwami.solve()
print("V_A =", sol.V("A"), " V_B =", sol.V("B"))
""")
    L.save()


def lesson05():
    L = Lesson(C, "05-prad-zmienny", "5. Prąd zmienny")
    L.md("""
# Prąd zmienny: wskazy

Przy napięciu sinusoidalnym kondensator i cewka zachowują się jak „opory”, które zależą od
częstotliwości — **impedancje**:

$$Z_C = \\frac{1}{j\\omega C} \\qquad Z_L = j\\omega L \\qquad \\omega = 2\\pi f$$

`solve(omega=...)` liczy obwód metodą **wskazów** (liczb zespolonych): moduł to amplituda, a argument —
przesunięcie fazy. Bez `omega` liczony jest stan ustalony przy prądzie stałym (kondensator to przerwa,
cewka — przewód).
""")
    L.code("""
import math
f = 50
rc = supply(10) + Resistor(1000) + node("wy") + shunt(Capacitor("3.3u"))
wy = rc.solve(omega=2 * math.pi * f).V("wy")
print("U_wy =", complex(wy))
print(f"amplituda {abs(complex(wy)):.2f} V, faza {math.degrees(math.atan2(complex(wy).imag, complex(wy).real)):.1f}°")
""")
    L.md("""
## Charakterystyka filtru

Filtr RC przepuszcza niskie częstotliwości, a tłumi wysokie. Częstotliwość graniczna
$f_g = \\frac{1}{2\\pi RC} \\approx 48$ Hz — tam zostaje $\\frac{1}{\\sqrt 2} \\approx 71\\%$ amplitudy:
""")
    L.code("""
for f in [5, 20, 48, 100, 500, 2000]:
    wy = complex(rc.solve(omega=2 * math.pi * f).V("wy"))
    print(f"{f:>5} Hz: {abs(wy) / 10 * 100:5.1f}% ", "█" * round(abs(wy) * 4))
""")
    L.md("""
## Rezonans

Cewka i kondensator razem mają częstotliwość, przy której ich impedancje się znoszą:
$f_0 = \\frac{1}{2\\pi\\sqrt{LC}}$. W obwodzie szeregowym RLC prąd jest wtedy największy:
""")
    L.code("""
L_, C_ = 0.01, 1e-6
f0 = 1 / (2 * math.pi * math.sqrt(L_ * C_))
print(f"f0 = {f0:.0f} Hz")
rlc = loop(VoltageSource(1), Resistor(10), Inductor(L_), Capacitor(C_))
for f in [0.5 * f0, 0.9 * f0, f0, 1.1 * f0, 2 * f0]:
    i = abs(complex(rlc.solve(omega=2 * math.pi * f)["R_1"].I))
    print(f"{f:7.0f} Hz: I = {i * 1000:6.2f} mA")
""")
    L.save()


def lesson06():
    L = Lesson(C, "06-twierdzenia", "6. Thévenin, Norton i czarne skrzynki")
    L.md("""
# Twierdzenia o obwodach

**Twierdzenie Thévenina:** każdy liniowy obwód widziany z dwóch zacisków zachowuje się jak jedno źródło
napięcia $E_{th}$ z jednym opornikiem $R_{th}$. **Norton:** albo jak źródło prądu z opornikiem
równolegle. To ogromne uproszczenie: zamiast liczyć cały obwód dla każdego obciążenia, liczysz go raz.

`equivalent(obwod)` znajduje $E_{th}$ i $R_{th}$ obwodu „1 zacisk wychodzi”, a `resistance()` — opór
zastępczy.
""")
    L.code("""
zrodlo = supply(12) + Resistor(10) + shunt(Resistor(10)) + Resistor(5)
equivalent(zrodlo)
""")
    L.md("""
Dzielnik 12 V z dwóch oporników 10 Ω i szeregowy 5 Ω to dla obciążenia po prostu 6 V przez 10 Ω.
Sprawdź: obciążenie 10 Ω dostanie połowę z 6 V — 3 V.
""")
    L.code("""
(zrodlo + Resistor(10, label="R_obc") + ground).solve()["R_obc"]
""")
    L.md("""
## Czarna skrzynka

`blackbox(obwod)` eliminuje wszystko, co jest w środku, i zostawia tylko **relację na zaciskach**:
równania wiążące napięcia i prądy na brzegach. Dwa obwody są równoważne dokładnie wtedy, gdy mają tę
samą czarną skrzynkę — tak wyrażają się twierdzenia Thévenina i Nortona.
""")
    L.code("""
blackbox(Resistor(10) | Resistor(10))
""")
    L.code("""
blackbox(Resistor(5))
""")
    L.md("""
Obie skrzynki są identyczne: dwa oporniki 10 Ω równolegle i jeden opornik 5 Ω są — widziane z zacisków —
tym samym obwodem.
""")
    L.save()


def lesson07():
    L = Lesson(C, "07-symulacja-z-kodu", "7. Symulacja w czasie z kodu")
    L.md("""
# `simulate()`

Obwody z diodami, tranzystorami i układami scalonymi liczy się w czasie. `simulate(obwod, t=...)` liczy
przebiegi od chwili włączenia (kondensatory puste) do czasu `t` sekund i zwraca **ślad**:

- `slad.at(0.5)` — wszystkie wielkości w chwili 0,5 s (słownik),
- `slad["I_R_1"]`, `slad.V("A")`, `slad.U("C_1")` — cały przebieg jednej wielkości,
- `slad.plot("V_A", "I_R_1")` — wykres.

Elementy „tylko w czasie” to m.in. `Diode()`, `LED("green")`, `Zener(5.1)`, `NPN()`, `PNP()`, `NMOS()`,
`PMOS()`, `Timer555()`, `Lamp(12)`, `Motor()`, `Relay()`, bramki `AND()`, `OR()`, `NOT()`, `XOR()`,
`NAND()`, `NOR()` i źródła `SineSource(amplituda, frequency=...)`, `SquareSource(poziom, frequency=..., duty=...)`.
""")
    L.code("""
prostownik = net(
    (SineSource(10, frequency=50), "GND", "we"),
    (Diode(), "we", "wy"),
    (Capacitor("220u"), "wy", "GND"),
    (Resistor(1000), "wy", "GND"),
)
slad = simulate(prostownik, t=0.1)
print("tętnienia:", round(max(slad.V("wy")[-400:]) - min(slad.V("wy")[-400:]), 2), "V")
slad.plot("V_we", "V_wy")
""")
    L.md("""
## Wejścia

Łączniki, przyciski, potencjometry i czujniki mają **wejścia**, które podajesz w `inputs`: liczbą albo
funkcją czasu. Nazwy: `S_1_closed` (0/1), `P_1_position` (0–1), `LDR_1_lux`, `RT_1_temperature`.
Tu łącznik zamyka się po 10 ms, a silnik rusza:
""")
    L.code("""
naped = net((VoltageSource(6), "GND", "a"), (Switch(), "a", "b"), (Motor(), "b", "GND"))
slad = simulate(naped, t=0.3, inputs={"S_1_closed": lambda t: 1 if t > 0.01 else 0})
print(f"obroty po 0,3 s: {slad.at(0.3)['w_M_1'] * 60 / 6.283:.0f} obr./min")
slad.plot("I_M_1")
""")
    L.md("""
## Bramki logiczne

Bramki pracują przy 5 V względem masy. Pierścień z trzech negacji i kondensatorów to **generator**:
każda bramka odwraca sygnał poprzedniej, a kondensatory opóźniają zmiany — więc stan nigdy się nie
ustala.
""")
    L.code("""
pierscien = net(
    (NOT(), "a", "b1"), (Resistor(1000), "b1", "b"), (Capacitor("1u"), "b", "GND"),
    (NOT(), "b", "c1"), (Resistor(1000), "c1", "c"), (Capacitor("1u"), "c", "GND"),
    (NOT(), "c", "a1"), (Resistor(1000), "a1", "a"), (Capacitor("1u"), "a", "GND"),
)
simulate(pierscien, t=0.02).plot("V_a")
""")
    L.save()


def lesson08():
    L = Lesson(C, "08-schematy-w-kodzie", "8. Schematy w kodzie")
    L.md("""
# Schematy w kodzie

Każdy schemat z notatki jest w kodzie zmienną o swojej nazwie — obiektem `Schematic`. Działa na nim
wszystko, co na obwodzie z kodu: `.solve()`, `simulate()`, `code()`, `schematic()`. Nazwa ze spacjami
i polskimi znakami zamienia się w zmienną bez nich: „Układ 1” to `układ1`. Można też sięgnąć po
schemat po nazwie: `schemat("Układ 1")`.

`schematic(obwod, sol)` rysuje obwód z wynikami rozwiązania przy elementach — do sprawozdania:
""")
    L.code("""
zadanie = loop(VoltageSource(12), Resistor(4), Resistor(2) | Resistor(3))
schematic(zadanie, zadanie.solve())
""")
    L.md("""
## `layout()`: kod → rysunek

`layout(obwod)` układa obwód z kodu na siatce i zwraca `Schematic` — ten sam rodzaj obiektu, co
narysowany ręcznie. Można go dalej zmieniać: przesuwać elementy, obracać, zapisać do JSON-a:
""")
    L.code("""
rys = layout(supply(9) + Resistor(100) + (Resistor(200) | Resistor(300)) + ground)
print([(e.id, e.kind, e.at) for e in rys.elements])
rys.move("R_1", (6, -2))
rys
""")
    L.save()


def lesson09():
    L = Lesson(C, "09-teoria", "9. Teoria: obwody jako kategoria")
    L.md("""
# Co jest pod spodem

Ta lekcja jest dla ciekawych — nie trzeba jej znać, żeby korzystać z biblioteki. `electro` traktuje
obwody jako **morfizmy kategorii hipergrafowej**. Brzmi groźnie, ale znaczy coś prostego: obwód to
„pudełko z zaciskami po lewej i prawej”, a jedyne, co z pudełkami robimy, to składanie.

```
Obwód (drzewo składni)  ──netlista──►  Netlista (kospan)  ──semantyka──►  równania / relacje
```

- **Obiekty** to liczby naturalne — ile zacisków. **Morfizmy** to obwody: $m \\to n$.
- `f + g` to **złożenie** (szeregowo): prawe zaciski `f` sklejone z lewymi `g`.
- `f @ g` to **iloczyn monoidalny**: obok siebie, bez połączenia.
- **Węzeł** to *pająk* algebry Frobeniusa: `split` rozdziela jeden przewód na dwa, `join` łączy dwa
  w jeden. Równanie $\\mathrm{split} + \\mathrm{join} = \\mathrm{wire}$ to fizycznie I prawo Kirchhoffa
  (prądy się sumują) i to, że węzeł ma jeden potencjał.
- **Równolegle** nie jest osobnym działaniem, tylko skrótem: `f | g = split + (f @ g) + join`.
- `f.transpose()` zamienia lewą stronę z prawą (*sztylet*).
""")
    L.code("""
rownolegle = split + (Resistor(10) @ Resistor(10)) + join
print("split + (R @ R) + join:", resistance(rownolegle), "Ω")
print("R | R:                 ", resistance(Resistor(10) | Resistor(10)), "Ω")
""")
    L.md("""
## Semantyka

Każdy element to **relacja** między potencjałami i prądami na zaciskach (opornik: $U = RI$), a obwód
złożony z elementów — relacja złożona z relacji. `blackbox` eliminuje zmienne wewnętrzne i zostawia
relację na brzegu: dwa obwody są równoważne, gdy mają tę samą czarną skrzynkę. Złożenie w kategorii
obwodów przechodzi na złożenie relacji — dlatego solver może pracować na dowolnie złożonych kawałkach
i zawsze dostanie ten sam wynik, jakby liczył całość.

**Netlista** to kospan: zaciski lewe → węzły ← zaciski prawe. Złożenie `+` to wypchnięcie (*pushout*):
sklejenie węzłów. Schemat narysowany na siatce jest jeszcze jedną składnią tego samego — dwa zaciski
w tym samym punkcie siatki to jeden węzeł, dokładnie jak dwa zaciski z tą samą nazwą w `net(...)`.

Po więcej: John Baez i Brendan Fong, *A Compositional Framework for Passive Linear Networks* (2015).
""")
    L.save()


def lesson10():
    L = Lesson(C, "10-analizy-i-zadania", "10. Analizy i zadania")
    L.md("""
# Analizy i zadania

Poza rozwiązaniem jednego układu `electro` robi kilka analiz, które liczą ten sam układ setki razy —
szybko, bo układ jest kompilowany raz, a potem tylko podstawiane są liczby.

## Charakterystyka częstotliwościowa

`bode(układ)` rysuje wzmocnienie w dB i fazę od 10 Hz do 1 MHz, z zaznaczoną częstotliwością graniczną
$f_g$ (−3 dB). Domyślnie dla nazwanych węzłów, względem źródła. Na schemacie to samo robi przycisk ∿.
""")
    L.code("""
filtr = supply(1) + Resistor("1k") + node("wy") + Capacitor("1u") + ground
r = bode(filtr)
print("f_g =", round(r.cutoffs()[0]), "Hz")
r
""")
    L.circuit("filtr_rc", supply(1) + Resistor("1k") + node("wy") + Capacitor("1u") + ground)
    L.md("""
## Zmiana wartości elementu

`sweep(układ, "R_2", (od, do))` pokazuje, jak wyjścia zależą od wartości jednego elementu:
""")
    L.code("""
dzielnik = supply(12) + Resistor("1k") + node("A") + Resistor() + ground
sweep(dzielnik, "R_2", ("100", "10k"))
""")
    L.md("""
## Tolerancje

Prawdziwe oporniki mają tolerancję (np. ±5 %). `tolerance()` buduje układ setki razy z losowymi
wartościami w tych granicach i pokazuje, jak bardzo rozrzuca się wynik:
""")
    L.code("""
tolerance(supply(12) + Resistor("10k") + node("A") + Resistor("10k") + ground, tol=0.05)
""")
    L.md("""
## Trójfazówka

`three_phase(230)` to źródło w gwiazdę (fazy 0°, −120°, 120°), a `star(...)` i `delta(...)` to odbiorniki.
Łączą się po nazwach węzłów `L1`, `L2`, `L3` i `N`. Fazory wpisuje się też wprost: `"230∠-120"`.
""")
    L.code("""
nierowna = three_phase(230) | star(Resistor(10), Resistor(20), Resistor(30))
nierowna.solve(omega=314)
""")
    L.md("""
## SPICE

`to_spice()` zapisuje układ jako netlistę dla ngspice albo LTspice, a `from_spice()` wczytuje netlistę
(w LTspice: *View → SPICE Netlist*). Wklejona w widok kodu schematu od razu się rysuje.
""")
    L.code("""
print(to_spice(filtr))
""")
    L.md("""
## Zadania do sprawdzenia

`task(układ, "I_R_1", "treść")` pokazuje treść i pole na odpowiedź. Odpowiedź jest sprawdzana w
przeglądarce z dokładnością 1 %, a w notatce zapisany jest tylko jej skrót — nie widać jej ani na stronie,
ani w pliku. Wpisz wynik (np. `0,4` albo `400 mA`) i kliknij **Sprawdź**.
""")
    L.code("""
task(supply(12) + Resistor(10) + Resistor(20) + ground, "I_R_1", "Jaki prąd płynie przez oba oporniki?")
""")
    L.save()


if __name__ == "__main__":
    intro()
    for lesson in (lesson01, lesson02, lesson04, lesson05, lesson06, lesson07, lesson08, lesson09, lesson10):
        lesson()
