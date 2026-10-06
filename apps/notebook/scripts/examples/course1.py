"""Kurs 1: elektronika od zera — od tego, czym jest prąd, do pierwszego programu na Arduino."""

from lib import A, Drawing, Lesson, course

C = "1-elektronika"


def intro():
    course(
        C,
        "Elektronika od zera",
        "Od tego, czym jest prąd i napięcie, przez prawo Ohma, kondensatory, diody i tranzystory, do bramek "
        "logicznych i pierwszego programu na Arduino. Każda lekcja ma obwód, który uruchamiasz, przełączasz "
        "i psujesz — bez lutownicy i bez strachu.",
    )


def flashlight(switch_closed=True) -> Drawing:
    """A battery, a switch and a bulb: a flashlight."""
    d = Drawing()
    d.add("E_1", "voltage_source", (0, 6), 270, "6")
    d.add("S_1", "switch", (2, 0), 0, None, "closed" if switch_closed else None)
    d.add("H_1", "lamp", (10, 0), 90, "12", "3")
    d.wire((0, 2), (0, 0), (2, 0))
    d.wire((6, 0), (10, 0))
    d.wire((10, 4), (10, 6), (0, 6))
    d.ground((0, 6))
    return d


def lesson01():
    L = Lesson(C, "01-prad-i-napiecie", "1. Prąd, napięcie i obwód")
    L.md("""
# Prąd, napięcie i obwód

Wszystko wokół jest zbudowane z atomów, a w atomach są **elektrony** — maleńkie cząstki z ładunkiem
elektrycznym. W metalach część elektronów nie siedzi na swoim miejscu, tylko swobodnie wędruje. Kiedy coś
je popchnie w jedną stronę, płyną wszystkie naraz, jak woda w rurze. Ten przepływ to **prąd elektryczny**.

Co je popycha? **Napięcie**. Bateria ma dwa bieguny: na jednym ma nadmiar elektronów, na drugim ich
brakuje. Ta różnica to napięcie — im większa, tym mocniej bateria pcha prąd. Napięcie mierzymy w
**woltach** (V), prąd w **amperach** (A).

| wielkość | co to jest | jak w wodzie | jednostka |
|---|---|---|---|
| napięcie $U$ | jak mocno coś pcha ładunki | ciśnienie wody | wolt, V |
| prąd $I$ | ile ładunku przepływa w sekundę | ile litrów na sekundę płynie rurą | amper, A |
| opór $R$ | jak bardzo coś utrudnia przepływ | wąska rura | om, Ω |
""")
    L.md("""
## Obwód musi być zamknięty

Prąd płynie tylko w **zamkniętej pętli**: z baterii, przez przewody i żarówkę, z powrotem do baterii.
Wystarczy jedna przerwa — i prąd nie płynie nigdzie. Tak działa każdy wyłącznik światła: rozcina pętlę.

Poniżej jest latarka: bateria $E_1$ (6 V), łącznik $S_1$ i żarówka $H_1$. Kreska z trzema poziomymi
liniami na dole to **masa** — umówiony punkt odniesienia, „zero” napięcia.

**Spróbuj:** kliknij ⚡ (symulacja w czasie), a potem kliknij łącznik $S_1$. Żarówka
gaśnie i zapala się, a kolor przewodów pokazuje napięcie: zielony to plus, szary to zero.
""")
    L.drawing("latarka", flashlight(), solve=True, live=True)
    L.md("""
Liczby przy elementach policzył przycisk ▶ (**Oblicz**): przez żarówkę płynie $0{,}5$ A, a napięcie na
niej to całe 6 V baterii. Łącznik jest zamknięty, więc na nim napięcia nie ma wcale — jest jak kawałek
przewodu.

Te same wyniki możesz dostać w komórce z kodem. Schemat ma nazwę `latarka` i pod tą nazwą jest widoczny
w kodzie:
""")
    L.code("""
sol = solve(latarka)
print("prąd żarówki:", sol("I_H_1"), "A")
print("napięcie na żarówce:", sol("U_H_1"), "V")
""")
    L.md("""
## Przedrostki

Prądy w elektronice bywają bardzo małe, a opory bardzo duże, dlatego używamy przedrostków — tak jak
w „kilogramie” czy „milimetrze”:

- **m** (mili) — tysięczna część: $20\\,\\mathrm{mA} = 0{,}02\\,\\mathrm{A}$,
- **µ** (mikro) — milionowa: $100\\,\\mathrm{µF} = 0{,}0001\\,\\mathrm{F}$,
- **k** (kilo) — tysiąc: $4{,}7\\,\\mathrm{kΩ} = 4700\\,Ω$,
- **M** (mega) — milion: $1\\,\\mathrm{MΩ} = 1\\,000\\,000\\,Ω$.

W aplikacji wpisujesz je tak samo: `20m`, `100u`, `4.7k` (albo `4k7`), `1M`.

## Spróbuj sam

1. Zaznacz baterię i zmień jej napięcie na 3 V, a potem kliknij ▶. Jaki prąd płynie teraz?
2. Uruchom symulację po zmianie — żarówka świeci słabiej, bo dostaje mniej mocy.
3. Usuń jeden przewód (zaznacz go i naciśnij Delete). Co się stało z prądem?
""")
    L.save()


def lesson02():
    L = Lesson(C, "02-prawo-ohma", "2. Opór i prawo Ohma")
    L.md("""
# Opór i prawo Ohma

**Opornik** (rezystor) to element, który utrudnia przepływ prądu. Im większy opór, tym mniejszy prąd przy
tym samym napięciu. Związek między nimi odkrył Georg Ohm w 1827 roku:

$$U = R \\cdot I$$

Napięcie na oporniku to jego opór razy prąd, który przez niego płynie. Można to przekształcić na dwa
pozostałe sposoby — i to są trzy najczęściej używane wzory w całej elektronice:

$$I = \\frac{U}{R} \\qquad R = \\frac{U}{I}$$

Przykład: bateria 9 V i opornik 1 kΩ. Prąd: $I = \\frac{9\\,\\mathrm{V}}{1000\\,Ω} = 9\\,\\mathrm{mA}$.
""")
    L.md("""
## Mierniki

Żeby to sprawdzić, potrzebujemy mierników:

- **amperomierz** ($A$) mierzy prąd, więc wstawia się go **w** obwód, szeregowo — prąd musi przez niego
  przepłynąć,
- **woltomierz** ($V$) mierzy napięcie między dwoma punktami, więc dołącza się go **obok** elementu,
  równolegle.

Kliknij ▶ **Oblicz**, żeby zobaczyć, co pokazują.
""")
    d = Drawing()
    d.add("E_1", "voltage_source", (0, 6), 270, "9")
    d.add("A_1", "ammeter", (2, 0), 0)
    d.add("R_1", "resistor", (10, 0), 90, "1k")
    d.add("V_1", "voltmeter", (14, 0), 90)
    d.wire((0, 2), (0, 0), (2, 0))
    d.wire((6, 0), (10, 0))
    d.wire((10, 0), (14, 0))
    d.wire((10, 4), (10, 6), (0, 6))
    d.wire((14, 4), (14, 6), (10, 6))
    d.ground((0, 6))
    L.drawing("pomiar", d, solve=True)
    L.md("""
## Im większy opór, tym mniejszy prąd

Ten sam obwód można zapisać kodem — tu dla kilku różnych oporników naraz. Najpierw elementy: bateria
`E` i opornik `R`. `~(E >> R)` to pętla z nich, a `Problem(obwód, {dane})` daje im wartości; `solve`
rozwiązuje, a `I(R)` to prąd opornika:
""")
    L.code("""
E, R = VoltageSource("E"), Resistor("R")
for r in [100, 470, 1000, 4700, 10000]:
    sol = solve(Problem(~(E >> R), {E: 9, R: r}))
    print(f"R = {r:>6} Ω   I = {float(sol(I(R))) * 1000:6.2f} mA")
""")
    L.md("""
## Opór nieznany

Często jest odwrotnie: znamy napięcie, zmierzyliśmy prąd, a chcemy wiedzieć, jaki to opornik. Zostaw
wartość opornika **pustą** — to znaczy „nie wiem” — a w amperomierzu wpisz odczyt, 20 mA. Solver sam
użyje prawa Ohma: $R = \\frac{U}{I} = \\frac{9\\,\\mathrm{V}}{0{,}02\\,\\mathrm{A}} = 450\\,Ω$.
""")
    d = Drawing()
    d.add("E_1", "voltage_source", (0, 6), 270, "9")
    d.add("A_1", "ammeter", (2, 0), 0, "20m")
    d.add("R_1", "resistor", (10, 0), 90)
    d.wire((0, 2), (0, 0), (2, 0))
    d.wire((6, 0), (10, 0))
    d.wire((10, 4), (10, 6), (0, 6))
    d.ground((0, 6))
    L.drawing("nieznany", d, solve=True)
    L.md("A tak wygląda to samo rozwiązanie krok po kroku, z uzasadnieniem każdego kroku:")
    L.code("""
steps(solve(nieznany))
""")
    L.md("""
## Spróbuj sam

1. W schemacie `pomiar` zmień opornik na 4,7 kΩ (wpisz `4.7k`). Ile pokazuje amperomierz?
2. W schemacie `nieznany` wpisz odczyt amperomierza `90m`. Jaki wyszedł opór?
3. Prawo Ohma działa w każdą stronę: jakie napięcie jest potrzebne, żeby przez 220 Ω popłynęło 15 mA?
   Policz w komórce z kodem: `220 * 0.015`.
""")
    L.save()


def lesson03():
    L = Lesson(C, "03-szeregowo-i-rownolegle", "3. Połączenia szeregowe i równoległe")
    L.md("""
# Szeregowo i równolegle

Elementy można połączyć na dwa podstawowe sposoby.

**Szeregowo** — jeden za drugim, w jednej ścieżce. Przez każdy płynie **ten sam prąd**, a napięcie baterii
dzieli się między nie. Opory się sumują:

$$R = R_1 + R_2$$

**Równolegle** — obok siebie, każdy podłączony wprost do baterii. Każdy dostaje **to samo napięcie**,
a prąd z baterii dzieli się między gałęzie. Opór zastępczy jest mniejszy od najmniejszego z nich:

$$\\frac{1}{R} = \\frac{1}{R_1} + \\frac{1}{R_2}$$
""")
    L.md("""
## Dwie żarówki szeregowo

Każda żarówka dostaje tylko połowę napięcia, 3 V, więc płynie przez nie połowa prądu i świecą słabo —
każda bierze tylko ćwierć swojej mocy. Uruchom ⚡ i porównaj z następnym schematem.
""")
    d = Drawing()
    d.add("E_1", "voltage_source", (0, 6), 270, "6")
    d.add("H_1", "lamp", (4, 0), 0, "12", "3")
    d.add("H_2", "lamp", (10, 0), 0, "12", "3")
    d.wire((0, 2), (0, 0), (4, 0))
    d.wire((8, 0), (10, 0))
    d.wire((14, 0), (16, 0), (16, 6), (0, 6))
    d.ground((0, 6))
    L.drawing("szeregowo", d, solve=True, live=True)
    L.md("""
## Dwie żarówki równolegle

Tu każda dostaje pełne 6 V i świeci jasno. Za to bateria oddaje dwa razy więcej prądu niż do jednej
żarówki — i szybciej się rozładuje. Tak podłączone jest wszystko w domu: każde gniazdko ma pełne 230 V,
bez względu na to, ile urządzeń już działa.
""")
    d = Drawing()
    d.add("E_1", "voltage_source", (0, 6), 270, "6")
    d.add("H_1", "lamp", (6, 0), 90, "12", "3")
    d.add("H_2", "lamp", (12, 0), 90, "12", "3")
    d.wire((0, 2), (0, 0), (6, 0))
    d.wire((6, 0), (12, 0))
    d.wire((6, 4), (6, 6))
    d.wire((12, 4), (12, 6), (6, 6))
    d.wire((6, 6), (0, 6))
    d.ground((0, 6))
    L.drawing("rownolegle", d, solve=True, live=True)
    L.md("""
## Opór zastępczy w kodzie

W kodzie `>>` łączy szeregowo, a `|` równolegle. Każdy kawałek obwodu to **komponent**: `.component`
pokazuje, jak jego napięcie $U$ zależy od prądu $I$ — opór zastępczy wychodzi sam, nikt nie podaje wzoru:
""")
    L.code("""
R_1, R_2, R_3 = Resistor("R_1"), Resistor("R_2"), Resistor("R_3")
for nazwa, kawalek in [("szeregowo", R_1 >> R_2), ("równolegle", R_2 | R_3), ("mieszane", R_1 >> (R_2 | R_3))]:
    print(f"{nazwa}: {kawalek.component}")
""")
    L.md("""
## Spróbuj sam

1. Dodaj trzecią żarówkę równolegle (skopiuj $H_2$: zaznacz, ⌘C/Ctrl+C, ⌘V/Ctrl+V, i dołącz przewodami).
   Jaki prąd oddaje teraz bateria?
2. Choinkowe lampki bywały łączone szeregowo — dlaczego po przepaleniu jednej gasły wszystkie?
3. Policz w kodzie opór trzech oporników 1 kΩ połączonych równolegle.
""")
    L.save()


def lesson04():
    L = Lesson(C, "04-moc-i-energia", "4. Moc i energia")
    L.md("""
# Moc i energia

Prąd płynący przez element wykonuje pracę: żarówka świeci i grzeje, silnik się kręci, opornik się
nagrzewa. Jak szybko to się dzieje, mówi **moc**:

$$P = U \\cdot I$$

Mierzymy ją w **watach** (W). Z prawem Ohma daje to jeszcze dwa przydatne wzory:
$P = I^2 R$ i $P = \\frac{U^2}{R}$.

**Energia** to moc razy czas. Żarówka 3 W świecąca przez godzinę zużywa 3 watogodziny (Wh); licznik
w domu liczy kilowatogodziny, kWh.
""")
    L.md("""
Poniżej dwie żarówki na 12 V: mocna (12 Ω) i słaba (48 Ω). Kliknij ▶ i porównaj moce $P$ w tabeli pod
schematem. Która świeci jaśniej, gdy uruchomisz ⚡?
""")
    d = Drawing()
    d.add("E_1", "voltage_source", (0, 6), 270, "12")
    d.add("H_1", "lamp", (6, 0), 90, "12", "12")
    d.add("H_2", "lamp", (12, 0), 90, "48", "12")
    d.wire((0, 2), (0, 0), (6, 0))
    d.wire((6, 0), (12, 0))
    d.wire((6, 4), (6, 6))
    d.wire((12, 4), (12, 6), (6, 6))
    d.wire((6, 6), (0, 6))
    d.ground((0, 6))
    L.drawing("dwie_zarowki", d, solve=True, live=True)
    L.code("""
sol = solve(dwie_zarowki)
for h in ["H_1", "H_2"]:
    print(h, "P =", sol(f"P_{h}"), "W")
""")
    L.md("""
## Opornik też się grzeje

Każdy opornik ma dopuszczalną moc — zwykłe, małe oporniki tylko **0,25 W**. Jeśli podłączysz opornik
100 Ω wprost do 5 V, wydzieli się w nim $P = \\frac{5^2}{100} = 0{,}25\\,\\mathrm{W}$ — na granicy. Przy
12 V byłoby to 1,44 W: prawdziwy opornik by się przypalił.
""")
    L.code("""
E, R = VoltageSource("E"), Resistor("R")
for u in [5, 9, 12]:
    p = solve(Problem(~(E >> R), {E: u, R: 100}))(P(R))
    print(f"{u:>2} V na 100 Ω: {float(p):.2f} W", "— za dużo!" if p > 0.25 else "")
""")
    L.md("""
## Ile wytrzyma bateria?

Pojemność baterii podaje się w miliamperogodzinach (mAh). Bateria 2000 mAh da 20 mA przez 100 godzin —
albo 1 A przez 2 godziny. Dioda LED biorąca 10 mA świeciłaby z niej przez ponad 8 dni:
""")
    L.code("""
pojemnosc = 2000  # mAh
prad = 10  # mA
print(pojemnosc / prad, "godzin, czyli", round(pojemnosc / prad / 24, 1), "dni")
""")
    L.save()


def lesson05():
    L = Lesson(C, "05-prawa-kirchhoffa", "5. Prawa Kirchhoffa")
    L.md("""
# Prawa Kirchhoffa

Dwa proste prawa pozwalają policzyć każdy obwód — nawet taki, którego nie da się rozłożyć na „szeregowo”
i „równolegle”.

**I prawo (prądowe):** ile prądu wpływa do węzła, tyle z niego wypływa. Ładunek nie znika i nie bierze
się znikąd. Jeśli do rozgałęzienia wpływa 3 A, a jedną gałęzią odpływa 1 A, to drugą — 2 A.

**II prawo (napięciowe):** idąc wokół dowolnej zamkniętej pętli i dodając napięcia (źródła na plus,
spadki na elementach na minus), zawsze dostaniesz zero. To jak chodzenie po górach: wracając do punktu
startu, jesteś na tej samej wysokości.
""")
    L.md("""
Oto obwód z **dwoma** źródłami: nie da się go uprościć do jednego opornika. Kliknij ▶ — solver ułoży
równania z praw Kirchhoffa i je rozwiąże.
""")
    d = Drawing()
    d.add("E_1", "voltage_source", (0, 6), 270, "12")
    d.add("R_1", "resistor", (2, 0), 0, "4")
    d.add("R_2", "resistor", (8, 2), 90, "6")
    d.add("R_3", "resistor", (10, 0), 0, "3")
    d.add("E_2", "voltage_source", (16, 6), 270, "6")
    d.wire((0, 2), (0, 0), (2, 0))
    d.wire((6, 0), (8, 0))
    d.wire((8, 0), (10, 0))
    d.wire((8, 0), (8, 2))
    d.wire((14, 0), (16, 0), (16, 2))
    d.wire((8, 6), (0, 6))
    d.wire((16, 6), (8, 6))
    d.ground((0, 6))
    L.drawing("dwa_zrodla", d, solve=True)
    L.md("""
Każdy krok ma swoje uzasadnienie — przy niektórych zobaczysz właśnie „I prawo Kirchhoffa” albo
„II prawo Kirchhoffa”:
""")
    L.code("""
steps(solve(dwa_zrodla))
""")
    L.md("""
## Sprawdź I prawo sam

Prąd z $R_1$ wpływa do węzła u góry i rozdziela się na $R_2$ i $R_3$. Ich suma musi się zgadzać:
""")
    L.code("""
sol = solve(dwa_zrodla)
print("I_R_1 =", sol("I_R_1"), " I_R_2 + I_R_3 =", sol("I_R_2 + I_R_3"))
""")
    L.md("""
## Spróbuj sam

1. Zmień $E_2$ na 12 V. W którą stronę płynie teraz prąd przez $R_3$? (Ujemny wynik znaczy: w drugą
   stronę, niż zakładała strzałka.)
2. Odwróć $E_2$ — zaznacz i obróć dwa razy klawiszem R. Co się zmieniło?
""")
    L.save()


def lesson06():
    L = Lesson(C, "06-dzielnik-napiecia", "6. Dzielnik napięcia i czujniki")
    L.md("""
# Dzielnik napięcia

Dwa oporniki szeregowo dzielą napięcie w proporcji swoich oporów. Napięcie na dolnym:

$$U_{wy} = U \\cdot \\frac{R_2}{R_1 + R_2}$$

To jeden z najważniejszych układów: tak zmniejsza się napięcie, tak działają potencjometry i tak
odczytuje się większość czujników.
""")
    d = Drawing()
    d.add("E_1", "voltage_source", (0, 8), 270, "10")
    d.add("R_1", "resistor", (6, 0), 90, "1k")
    d.add("R_2", "resistor", (6, 4), 90, "4k")
    d.add("V_1", "voltmeter", (10, 4), 90)
    d.wire((0, 4), (0, 0), (6, 0))
    d.wire((6, 4), (10, 4))
    d.wire((6, 8), (0, 8))
    d.wire((10, 8), (6, 8))
    d.ground((0, 8))
    L.drawing("dzielnik", d, solve=True)
    L.md("""
Solver umie też liczyć na literach. Zamiast liczb wpisz symbole — dostaniesz wzór. `Node("wy")` to
nazwany punkt między opornikami, `GND` to masa, a `>>` łączy elementy jeden za drugim:
""")
    L.code("""
U_z, R_a, R_b, wy = VoltageSource("U"), Resistor("R_a"), Resistor("R_b"), Node("wy")
dz = Problem(GND >> U_z >> R_a >> wy >> R_b >> GND, {U_z: "U", R_a: "R_a", R_b: "R_b"})
solve(dz)(V(wy))
""")
    L.md("""
## Potencjometr

Potencjometr to opornik z suwakiem: jeden element, który jest od razu dzielnikiem. Przesuwając suwak,
zmieniasz proporcję. Uruchom ⚡, kliknij potencjometr i przesuwaj suwak (albo użyj zakładki
**Regulacja** pod schematem) — woltomierz pokazuje od 0 do 5 V.
""")
    d = Drawing()
    d.add("E_1", "voltage_source", (0, 6), 270, "5")
    d.add("P_1", "potentiometer", (4, 0), 0, "10k", "0.3")
    d.add("V_1", "voltmeter", (6, -2), 0)
    d.wire((0, 2), (0, 0), (4, 0))
    d.wire((8, 0), (12, 0), (12, 6), (0, 6))
    d.wire((10, -2), (14, -2), (14, 6), (12, 6))
    d.ground((0, 6))
    L.drawing("suwak", d, live=True)
    L.md("""
## Czujnik światła

**Fotorezystor** to opornik, którego opór maleje, gdy pada na niego światło: w ciemności ma dziesiątki
kiloomów, w słońcu kilkaset omów. W dzielniku zmienia się więc napięcie — i to napięcie może odczytać
Arduino. Uruchom ⚡, kliknij fotorezystor i zmieniaj światło.
""")
    d = Drawing()
    d.add("E_1", "voltage_source", (0, 8), 270, "5")
    d.add("R_1", "resistor", (6, 0), 90, "10k")
    d.add("LDR_1", "photoresistor", (6, 4), 90, "10k", "100")
    d.add("V_1", "voltmeter", (10, 4), 90)
    d.wire((0, 4), (0, 0), (6, 0))
    d.wire((6, 4), (10, 4))
    d.wire((6, 8), (0, 8))
    d.wire((10, 8), (6, 8))
    d.ground((0, 8))
    L.drawing("swiatlo", d, solve=True, live=True)
    L.md("""
## Spróbuj sam

1. W dzielniku zamień $R_2$ na 1 kΩ. Ile wychodzi teraz? (Równe oporniki dzielą napięcie na pół.)
2. Zamień miejscami opornik i fotorezystor w ostatnim schemacie. Co się dzieje z napięciem, gdy robi się
   ciemniej?
3. W kodzie zamień litery na liczby — `{U_z: 12, R_a: 1000, R_b: 2000}` — i sprawdź wzór.
""")
    L.save()


def lesson07():
    L = Lesson(C, "07-kondensator", "7. Kondensator")
    L.md("""
# Kondensator

**Kondensator** to dwie metalowe okładki rozdzielone izolatorem. Prąd nie może przez niego przepłynąć
na wylot, ale może na nim **gromadzić ładunek**: na jednej okładce zbiera się nadmiar elektronów, na
drugiej niedobór. Naładowany kondensator jest jak mała bateria — na krótko.

Ile ładunku zmieści, mówi jego **pojemność** $C$, w faradach (F). Farad to bardzo dużo; typowe
kondensatory mają nanofarady (nF) albo mikrofarady (µF).

Kondensator ładowany przez opornik nie ładuje się od razu, tylko coraz wolniej. Tempo wyznacza
**stała czasowa**:

$$\\tau = R \\cdot C$$

Po czasie $\\tau$ kondensator ma 63% napięcia, po $5\\tau$ jest praktycznie pełny.
""")
    L.md("""
## Dioda, która gaśnie powoli

Uruchom ⚡ i **przytrzymaj** przycisk $B_1$: kondensator ładuje się niemal od razu (przez mały opornik),
a dioda świeci. Puść przycisk — kondensator oddaje ładunek przez diodę, która gaśnie powoli, przez
mniej więcej sekundę. Oscyloskop pod schematem pokazuje, jak spada napięcie `V_c`.
""")
    d = Drawing()
    d.add("E_1", "voltage_source", (0, 8), 270, "5")
    d.add("B_1", "button", (2, 0), 0)
    d.add("R_1", "resistor", (6, 0), 0, "10")
    d.add("C_1", "capacitor", (12, 4), 90, "2200u")
    d.add("R_2", "resistor", (12, 0), 0, "470")
    d.add("LED_1", "led", (18, 2), 90, None, "yellow")
    d.wire((0, 4), (0, 0), (2, 0))
    d.wire((10, 0), (12, 0))
    d.wire((12, 0), (12, 4))
    d.wire((16, 0), (18, 0), (18, 2))
    d.wire((12, 8), (0, 8))
    d.wire((18, 6), (18, 8), (12, 8))
    d.ground((0, 8))
    d.label("c", (12, 0))
    L.drawing("gasnaca", d)
    L.md("""
## Ładowanie w kodzie

`simulate()` liczy obwód krok po kroku w czasie. Tu źródło ładuje kondensator 100 µF przez 10 kΩ:
$\\tau = 10\\,000 \\cdot 0{,}0001 = 1$ s. Na wykresie widać, że po sekundzie napięcie ma ok. 63% z 5 V,
czyli 3,16 V.
""")
    L.code("""
E, R, C, c = VoltageSource("E"), Resistor("R"), Capacitor("C"), Node("c")
rc = Problem(GND >> E >> R >> c >> C >> GND, {E: 5, R: "10k", C: "100u"})
przebieg = simulate(rc, until=5)
print("po 1 s:", round(przebieg.at("V_c", 1), 2), "V")
plot(przebieg, "V_c")
""")
    L.md("""
## Do czego to służy?

- **wygładzanie** — kondensator „łata” dziury w napięciu (np. w zasilaczu, lekcja o diodach),
- **odmierzanie czasu** — migacze i generatory (lekcja o NE555),
- **filtry** — przepuszczają szybkie albo wolne zmiany sygnału,
- **zapas energii** — lampa błyskowa w aparacie ładuje kondensator, a potem oddaje go w ułamku sekundy.

## Spróbuj sam

1. Zmień $C_1$ na 470 µF (`470u`). Jak długo gaśnie dioda teraz?
2. W kodzie zmień opornik na `20k`. Po jakim czasie napięcie dojdzie do 3,16 V?
""")
    L.save()


def lesson08():
    L = Lesson(C, "08-dioda-i-led", "8. Dioda i LED")
    L.md("""
# Dioda — zawór jednokierunkowy

**Dioda** przepuszcza prąd tylko w jedną stronę: od **anody** (trójkąt) do **katody** (kreska). W drugą
stronę jest prawie idealną przerwą. Żeby zaczęła przewodzić, potrzebuje małego napięcia — dla zwykłej
diody krzemowej ok. **0,7 V**.

**LED** (dioda świecąca) działa tak samo, ale świeci. Potrzebuje więcej napięcia: czerwona ok. 2 V,
zielona 2,2 V, niebieska i biała ok. 3 V.
""")
    L.md("""
## LED zawsze z opornikiem

Dioda nie ogranicza prądu sama: powyżej swojego napięcia przewodzi coraz mocniej i bez opornika by się
spaliła. Opornik dobiera się z prawa Ohma — na nim zostaje napięcie, którego nie weźmie dioda:

$$R = \\frac{U_{zas} - U_{LED}}{I_{LED}} = \\frac{5\\,\\mathrm{V} - 2\\,\\mathrm{V}}{0{,}02\\,\\mathrm{A}} = 150\\,Ω$$

Poniżej dwie diody z takim samym opornikiem, ale jedna jest odwrócona. Uruchom ⚡ — świeci tylko ta,
która jest ustawiona w kierunku przewodzenia.
""")
    d = Drawing()
    d.add("E_1", "voltage_source", (0, 8), 270, "5")
    d.add("R_1", "resistor", (6, 0), 90, "150")
    d.add("LED_1", "led", (6, 4), 90, None, "red")
    d.add("R_2", "resistor", (12, 0), 90, "150")
    d.add("LED_2", "led", (12, 8), 270, None, "green")
    d.wire((0, 4), (0, 0), (6, 0))
    d.wire((6, 0), (12, 0))
    d.wire((6, 8), (0, 8))
    d.wire((12, 8), (6, 8))
    d.ground((0, 8))
    L.drawing("kierunek", d)
    L.code("""
u_zas, u_led, i_led = 5, 2.0, 0.020
print("opornik:", (u_zas - u_led) / i_led, "Ω")
""")
    L.md("""
## Kolory mają różne napięcia

Trzy diody z tym samym opornikiem 150 Ω: niebieska potrzebuje najwięcej napięcia, więc zostaje mniej na
oporniku i płynie przez nią mniejszy prąd. W czasie symulacji wybierz narzędzie **miernik** i kliknij
każdą diodę, żeby zobaczyć jej prąd.
""")
    d = Drawing()
    d.add("E_1", "voltage_source", (0, 8), 270, "5")
    for k, (x, color) in enumerate([(6, "red"), (12, "green"), (18, "blue")]):
        d.add(f"R_{k + 1}", "resistor", (x, 0), 90, "150")
        d.add(f"LED_{k + 1}", "led", (x, 4), 90, None, color)
    d.wire((0, 4), (0, 0), (6, 0))
    d.wire((6, 0), (12, 0))
    d.wire((12, 0), (18, 0))
    d.wire((6, 8), (0, 8))
    d.wire((12, 8), (6, 8))
    d.wire((18, 8), (12, 8))
    d.ground((0, 8))
    L.drawing("kolory", d)
    L.md("""
## Dioda w zasilaczu: prostownik

Gniazdko daje prąd **zmienny**: kierunek zmienia się 50 razy na sekundę. Dioda przepuszcza tylko
połówki w jedną stronę, a kondensator wygładza dziury między nimi. Na oscyloskopie porównaj `V_we`
(sinusoida) i `V_wy` (prawie stałe napięcie z małymi „zębami”).
""")
    d = Drawing()
    d.add("E_1", "sine_source", (0, 8), 270, "12", "50")
    d.add("D_1", "diode", (2, 0), 0)
    d.add("C_1", "capacitor", (10, 4), 90, "470u")
    d.add("R_1", "resistor", (14, 4), 90, "1k")
    d.wire((0, 4), (0, 0), (2, 0))
    d.wire((6, 0), (10, 0), (10, 4))
    d.wire((10, 0), (14, 0), (14, 4))
    d.wire((10, 8), (0, 8))
    d.wire((14, 8), (10, 8))
    d.ground((0, 8))
    d.label("we", (0, 4))
    d.label("wy", (10, 0))
    L.drawing("prostownik", d)
    L.code("""
plot(simulate(prostownik, until=0.1), "V_we", "V_wy")
""")
    L.save()


def lesson09():
    L = Lesson(C, "09-tranzystor", "9. Tranzystor")
    L.md("""
# Tranzystor — mały prąd steruje dużym

**Tranzystor** to najważniejszy wynalazek elektroniki XX wieku. Ma trzy nóżki: **bazę** (B),
**kolektor** (C) i **emiter** (E). Mały prąd wpływający do bazy pozwala popłynąć nawet sto razy
większemu prądowi z kolektora do emitera. Bez prądu bazy tranzystor jest zamknięty.

Można go używać na dwa sposoby:

- jako **klucz** — włącza i wyłącza duży prąd małym (tak pracuje w tej lekcji),
- jako **wzmacniacz** — słaby sygnał na bazie steruje proporcjonalnie silnym prądem (zobacz w przykładach).

W procesorze komputera są miliardy tranzystorów pracujących jako klucze.
""")
    L.md("""
## Przycisk włącza żarówkę

Żarówka bierze 0,75 A — dużo za dużo dla małego przycisku. Przycisk steruje więc tylko prądem bazy
(ok. 8 mA przez $R_1$), a ciężką pracę wykonuje tranzystor. $R_2$ trzyma bazę przy masie, gdy przycisk
jest puszczony. Uruchom ⚡ i przytrzymaj $B_1$.
""")
    d = Drawing()
    d.add("E_1", "voltage_source", (0, 10), 270, "9")
    d.add("H_1", "lamp", (13, 0), 90, "12", "6.75")
    d.add("B_1", "button", (2, 3), 90)
    d.add("R_1", "resistor", (2, 8), 0, "1k")
    d.add("Q_1", "npn", (10, 8), 0)
    d.add("R_2", "resistor", (8, 10), 90, "10k")
    d.wire((0, 6), (0, 0), (13, 0))
    d.wire((2, 0), (2, 3))
    d.wire((2, 7), (2, 8))
    d.wire((6, 8), (8, 8))
    d.wire((8, 8), (10, 8))
    d.wire((8, 8), (8, 10))
    d.wire((13, 4), (13, 6))
    d.wire((13, 10), (13, 14), (8, 14))
    d.wire((8, 14), (0, 14), (0, 10))
    d.ground((0, 10))
    L.drawing("klucz", d)
    L.md("""
## Lampka nocna

Połącz dzielnik z fotorezystorem (lekcja 6) z tranzystorem, a dostaniesz lampkę, która sama zapala się
po zmroku: w ciemności fotorezystor ma duży opór, napięcie na bazie rośnie i tranzystor włącza diodę.
Potencjometrem ustawiasz, przy jakim świetle ma się zapalać. Uruchom ⚡ i zmieniaj światło na
fotorezystorze.
""")
    d = Drawing()
    d.add("E_1", "voltage_source", (0, 10), 270, "5")
    d.add("P_1", "potentiometer", (3, -2), 0, "100k", "0.3")
    d.add("LDR_1", "photoresistor", (6, 6), 90, "10k", "300")
    d.add("R_1", "resistor", (10, 4), 0, "10k")
    d.add("Q_1", "npn", (16, 4), 0)
    d.add("R_2", "resistor", (19, -6), 90, "220")
    d.add("LED_1", "led", (19, -2), 90, None, "white")
    d.connect(
        {
            "5V": [("E_1", 1), ("P_1", 0), ("R_2", 0)],
            "d": [("P_1", 1), ("P_1", 2), ("LDR_1", 0), ("R_1", 0)],
            "b": [("R_1", 1), ("Q_1", 0)],
            "led": [("R_2", 1), ("LED_1", 0)],
            "c": [("LED_1", 1), ("Q_1", 1)],
            "GND": [("E_1", 0), ("LDR_1", 1), ("Q_1", 2)],
        }
    )
    d.ground(d.pin("E_1", 0))
    L.drawing("lampka_nocna", d)
    L.md("""
## Spróbuj sam

1. W `klucz` zwiększ $R_1$ do 100 kΩ. Prąd bazy spada do 80 µA — czy żarówka jeszcze świeci pełnym
   blaskiem? (Tranzystor wzmacnia ok. 100 razy: 80 µA × 100 = 8 mA, a żarówka potrzebuje 750 mA.)
2. W lampce nocnej przekręć potencjometr. Przy jakim świetle zapala się teraz?
""")
    L.save()


def lesson10():
    L = Lesson(C, "10-cewka-przekaznik-silnik", "10. Cewka, przekaźnik i silnik")
    L.md("""
# Magnetyzm: cewka, przekaźnik, silnik

Prąd płynący przewodem wytwarza wokół niego **pole magnetyczne**. Nawinięty w **cewkę** — wiele zwojów
jeden obok drugiego — daje pole na tyle silne, że cewka staje się elektromagnesem. Na tym działają
przekaźniki, silniki, głośniki i transformatory.

Cewka ma jeszcze jedną cechę: **nie lubi zmian prądu**. Gdy prąd rośnie, hamuje go; gdy nagle znika,
cewka próbuje go podtrzymać — i potrafi przy tym wytworzyć bardzo wysokie napięcie.
""")
    L.md("""
## Silnik

W silniku prądu stałego elektromagnes obraca się między magnesami. Uruchom ⚡ i zamknij łącznik — silnik
rozpędza się (na początku bierze duży prąd, potem coraz mniejszy). Obróć źródło o 180° (zaznacz je
i naciśnij dwa razy R), a silnik zakręci się w drugą stronę.
""")
    d = Drawing()
    d.add("E_1", "voltage_source", (0, 6), 270, "6")
    d.add("S_1", "switch", (2, 0), 0)
    d.add("M_1", "motor", (10, 0), 90)
    d.wire((0, 2), (0, 0), (2, 0))
    d.wire((6, 0), (10, 0))
    d.wire((10, 4), (10, 6), (0, 6))
    d.ground((0, 6))
    L.drawing("silnik", d)
    L.code("""
rozruch = simulate(silnik, until=0.4, inputs={"S_1_closed": 1})
plot(rozruch, "I_M_1")
""")
    L.md("""
## Przekaźnik

**Przekaźnik** to przełącznik poruszany elektromagnesem. Mały prąd cewki (70 mA) przełącza styk, przez
który może płynąć duży prąd — i to w zupełnie innym obwodzie, nawet 230 V. W spoczynku styk COM łączy się
z NC (*normally closed*), a gdy cewka przyciągnie — z NO (*normally open*).

Uruchom ⚡ i przytrzymaj $B_1$: silnik staje, a zapala się żarówka. Dioda $D_1$ obok cewki jest tu
bardzo ważna — zaraz zobaczysz dlaczego.
""")
    d = Drawing()
    d.add("E_1", "voltage_source", (0, 8), 270, "5")
    d.add("B_1", "button", (3, -2), 0)
    d.add("K_1", "relay", (12, 0), 0)
    d.add("D_1", "diode", (8, 4), 270)
    d.add("E_2", "voltage_source", (30, 10), 270, "12")
    d.add("H_1", "lamp", (28, -8), 90, "24", "6")
    d.add("M_1", "motor", (19, -8), 90)
    d.connect(
        {
            "5V": [("E_1", 1), ("B_1", 0)],
            "coil": [("B_1", 1), ("K_1", 0), ("D_1", 1)],
            "12V": [("E_2", 1), ("K_1", 2)],
            "no": [("K_1", 4), ("H_1", 1)],
            "nc": [("K_1", 3), ("M_1", 1)],
            "GND": [("E_1", 0), ("K_1", 1), ("D_1", 0), ("E_2", 0), ("H_1", 0), ("M_1", 0)],
        }
    )
    d.ground(d.pin("E_1", 0))
    L.drawing("przekaznik", d)
    L.md("""
## Skok napięcia na cewce

Tu tranzystor włącza i wyłącza cewkę przekaźnika pięć razy na sekundę — ale **nie ma diody**. Gdy
tranzystor się zamyka, prąd cewki nie ma dokąd płynąć, a cewka „pcha” go dalej: napięcie na kolektorze
skacze na setki woltów. Prawdziwy tranzystor by tego nie przeżył. Wykres pokazuje napięcie na kolektorze
`V_c` — porównaj go z tym samym układem z diodą.
""")
    for diode in (False, True):
        d = Drawing()
        d.add("E_1", "voltage_source", (0, 12), 270, "5")
        d.add("E_2", "square_source", (4, 14), 270, "5", "5")
        d.add("R_1", "resistor", (6, 6), 0, "1k")
        d.add("Q_1", "npn", (12, 6), 0)
        d.add("K_1", "relay", (15, -4), 0)
        d.add("R_2", "resistor", (24, 0), 90, "1k")
        d.add("t1", "terminal", (19, -4), 0)
        nets = {
            "5V": [("E_1", 1), ("K_1", 0), ("K_1", 2)],
            "sq": [("E_2", 1), ("R_1", 0)],
            "b": [("R_1", 1), ("Q_1", 0)],
            "c": [("Q_1", 1), ("K_1", 1)],
            "no": [("K_1", 4), ("R_2", 0)],
            "GND": [("E_1", 0), ("E_2", 0), ("Q_1", 2), ("R_2", 1)],
        }
        if diode:
            d.add("D_1", "diode", (10, 0), 270)
            nets["5V"].append(("D_1", 1))
            nets["c"].append(("D_1", 0))
        d.connect(nets)
        d.ground(d.pin("E_1", 0))
        d.label("c", d.pin("Q_1", 1))
        name = "z_dioda" if diode else "bez_diody"
        L.drawing(name, d)
        L.code(f"""
plot(simulate({name}, until=0.4), "V_c")
""")
    L.save()


def lesson11():
    L = Lesson(C, "11-logika-cyfrowa", "11. Logika cyfrowa")
    L.md("""
# Zera i jedynki

Komputery nie liczą napięć z przecinkiem — rozróżniają tylko dwa stany: **niskie** napięcie (blisko 0 V)
to **0**, **wysokie** (blisko 5 V) to **1**. Tak jest odporniej: nieważne, czy jest 4,7 V, czy 5,1 V —
to i tak 1.

**Bramka logiczna** to mały układ z tranzystorów, który z wejść w stanach 0/1 robi wyjście 0/1 według
prostej reguły:

| wejścia A B | NOT A | AND | OR | XOR | NAND | NOR |
|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| 0 0 | 1 | 0 | 0 | 0 | 1 | 1 |
| 0 1 | 1 | 0 | 1 | 1 | 1 | 0 |
| 1 0 | 0 | 0 | 1 | 1 | 1 | 0 |
| 1 1 | 0 | 1 | 1 | 0 | 0 | 0 |

**AND** („i”) daje 1, gdy oba wejścia są 1. **OR** („lub”) — gdy choć jedno. **XOR** („albo”) — gdy są
różne. **NOT** odwraca. N przed nazwą znaczy: to samo, odwrócone. Na schematach bramki nie mają
narysowanego zasilania — tak się je rysuje w logice; tu pracują przy 5 V.
""")
    L.md("""
## Sprawdź tabelkę

Dwa przyciski ($A$ i $B$) sterują trzema bramkami naraz. Oporniki 10 kΩ trzymają wejścia na 0, dopóki
przycisk nie da im 5 V. Uruchom ⚡ i przytrzymuj przyciski (także oba naraz — przyciski mają przypisane
klawisze **A** i **B**: kliknij najpierw schemat).
""")
    d = Drawing()
    d.add("E_1", "voltage_source", (-4, 14), 270, "5")
    d.add("B_1", "button", (4, 2), 90, None, "a")
    d.add("B_2", "button", (8, 2), 90, None, "b")
    d.add("R_1", "resistor", (4, 10), 90, "10k")
    d.add("R_2", "resistor", (8, 10), 90, "10k")
    gates = [("U_1", "and_gate", 2), ("U_2", "or_gate", 8), ("U_3", "xor_gate", 14)]
    for k, (gid, kind, y) in enumerate(gates):
        d.add(gid, kind, (14, y - 1), 0)
        d.add(f"R_{k + 3}", "resistor", (18, y), 0, "220")
        d.add(f"LED_{k + 1}", "led", (24, y), 90, None, ["green", "yellow", "blue"][k])
    d.connect(
        {
            "5V": [("E_1", 1), ("B_1", 0), ("B_2", 0)],
            "a": [("B_1", 1), ("R_1", 0), ("U_1", 0), ("U_2", 0), ("U_3", 0)],
            "b": [("B_2", 1), ("R_2", 0), ("U_1", 1), ("U_2", 1), ("U_3", 1)],
            **{f"y{k}": [(gid, 2), (f"R_{k + 3}", 0)] for k, (gid, _, _) in enumerate(gates)},
            **{f"l{k}": [(f"R_{k + 3}", 1), (f"LED_{k + 1}", 0)] for k in range(3)},
            "GND": [("E_1", 0), ("R_1", 1), ("R_2", 1), *[(f"LED_{k + 1}", 1) for k in range(3)]],
        }
    )
    d.ground(d.pin("E_1", 0))
    L.drawing("bramki", d)
    L.md("""
## Pamięć z dwóch bramek

Połącz dwie bramki NOR „na krzyż” — wyjście każdej do wejścia drugiej — a dostaniesz **zatrzask**:
najprostszą pamięć, jeden bit. Krótkie naciśnięcie **S** (*set*) zapala diodę i dioda **zostaje
zapalona**, choć przycisk już puszczony. **R** (*reset*) ją gasi. Z milionów takich komórek zbudowana jest
pamięć komputera.
""")
    d = Drawing()
    d.add("E_1", "voltage_source", (-4, 16), 270, "5")
    d.add("B_1", "button", (4, 2), 90, None, "s")
    d.add("B_2", "button", (8, 2), 90, None, "r")
    d.add("R_1", "resistor", (4, 12), 90, "10k")
    d.add("R_2", "resistor", (8, 12), 90, "10k")
    d.add("U_1", "nor_gate", (14, 4), 0)
    d.add("U_2", "nor_gate", (14, 9), 0)
    d.add("R_3", "resistor", (24, 5), 0, "220")
    d.add("LED_1", "led", (30, 5), 90, None, "red")
    d.connect(
        {
            "5V": [("E_1", 1), ("B_1", 0), ("B_2", 0)],
            "s": [("B_1", 1), ("R_1", 0), ("U_1", 0)],
            "r": [("B_2", 1), ("R_2", 0), ("U_2", 0)],
            "qn": [("U_1", 2), ("U_2", 1)],
            "q": [("U_2", 2), ("U_1", 1), ("R_3", 0)],
            "led": [("R_3", 1), ("LED_1", 0)],
            "GND": [("E_1", 0), ("R_1", 1), ("R_2", 1), ("LED_1", 1)],
        }
    )
    d.ground(d.pin("E_1", 0))
    L.drawing("zatrzask", d)
    L.md("""
## Dodawanie

Jak dodać dwie jednobitowe liczby? $0+0=0$, $0+1=1$, $1+0=1$, $1+1=10$ (dwójkowo: „dwa” to „jeden
dalej, zero tutaj”). Cyfra wyniku to dokładnie XOR, a przeniesienie na następną pozycję to AND. Bramka
XOR i bramka AND razem to **półsumator** — schemat `bramki` powyżej już nim jest: dioda niebieska to
suma, zielona — przeniesienie. Tak liczy każdy procesor, tylko na 64 bitach naraz.
""")
    L.save()


def lesson12():
    L = Lesson(C, "12-generator-555", "12. Generator: NE555")
    L.md("""
# Układ scalony NE555

Wszystko, co do tej pory było osobno — tranzystory, oporniki, bramki — można zmieścić w jednym kawałku
krzemu. Tak powstaje **układ scalony**. NE555 (1972) to jeden z najpopularniejszych w historii: w środku
ma dwa komparatory i przerzutnik, a z kilkoma elementami na zewnątrz staje się **generatorem**.

Kondensator $C_1$ ładuje się przez $R_1 + R_2$ do ⅔ napięcia zasilania, a potem rozładowuje przez $R_2$
do ⅓ — i tak w kółko. Wyjście (pin 3) jest wysokie w czasie ładowania i niskie przy rozładowaniu:

$$f \\approx \\frac{1{,}44}{(R_1 + 2R_2)\\,C_1}$$

Uruchom ⚡: dioda mruga ok. 0,7 razy na sekundę, a oscyloskop pokazuje piłę na kondensatorze.
""")
    d = Drawing()
    d.add("E_1", "voltage_source", (0, 14), 270, "9")
    d.add("IC_1", "timer555", (10, 2), 0)
    d.add("R_1", "resistor", (6, 0), 90, "1k")
    d.add("R_2", "resistor", (6, 6), 90, "10k")
    d.add("C_1", "capacitor", (6, 10), 90, "100u")
    d.add("C_2", "capacitor", (14, 8), 90, "10n")
    d.add("R_3", "resistor", (16, 5), 0, "330")
    d.add("LED_1", "led", (20, 5), 90, None, "red")
    d.wire((0, 10), (0, 0), (6, 0))
    d.wire((6, 0), (12, 0))
    d.wire((12, 0), (14, 0))
    d.wire((12, 2), (12, 0))
    d.wire((14, 2), (14, 0))
    d.wire((6, 4), (6, 6))
    d.wire((6, 6), (10, 6))
    d.wire((10, 4), (9, 4), (9, 5), (10, 5))
    d.wire((6, 10), (9, 10), (9, 5))
    d.wire((0, 14), (6, 14))
    d.wire((6, 14), (12, 14))
    d.wire((12, 14), (14, 14))
    d.wire((14, 14), (20, 14))
    d.wire((12, 8), (12, 14))
    d.wire((14, 12), (14, 14))
    d.wire((20, 9), (20, 14))
    d.ground((0, 14))
    d.label("c", (6, 10))
    L.drawing("migacz", d)
    L.code("""
R1, R2, C1 = 1_000, 10_000, 100e-6
f = 1.44 / ((R1 + 2 * R2) * C1)
print(f"f = {f:.2f} Hz, okres {1 / f:.2f} s")
plot(simulate(migacz, until=6), "V_c")
""")
    L.md("""
## Spróbuj sam

1. Zmień $C_1$ na 10 µF. Dioda miga dziesięć razy szybciej.
2. Zamień diodę na buzzer pasywny, a $C_1$ na 100 nF: 555 zagra dźwięk ok. 690 Hz.
3. Zamiast $R_2$ wstaw potencjometr 100 kΩ (dwa zaciski: jeden koniec i suwak) — i reguluj tempo.
""")
    L.save()


BLINK = """// Mruganie: dioda na pinie 13 zapala się i gaśnie co pół sekundy.
// setup() wykonuje się raz, na starcie; loop() — w kółko, bez końca.

void setup() {
  pinMode(13, OUTPUT);     // pin 13 będzie wyjściem
  Serial.begin(9600);      // port szeregowy: napisy widać pod schematem
}

void loop() {
  digitalWrite(13, HIGH);  // 5 V na pinie: dioda świeci
  Serial.println("swieci");
  delay(500);              // czekaj 500 ms
  digitalWrite(13, LOW);   // 0 V: gaśnie
  Serial.println("zgaszona");
  delay(500);
}
"""

INPUTS = """// Przycisk na D2 zapala diodę na D13, a potencjometr na A0 ustawia jasność diody na D9.

void setup() {
  pinMode(2, INPUT_PULLUP);  // wejście z opornikiem do 5 V w środku: puszczony = HIGH
  pinMode(13, OUTPUT);
  pinMode(9, OUTPUT);
  Serial.begin(9600);
}

void loop() {
  bool wcisniety = digitalRead(2) == LOW;  // przycisk zwiera pin do masy
  digitalWrite(13, wcisniety ? HIGH : LOW);

  int odczyt = analogRead(A0);        // 0–1023, czyli 0–5 V
  analogWrite(9, odczyt / 4);          // PWM: 0–255
  Serial.print("A0 = ");
  Serial.print(odczyt * 5.0 / 1023);
  Serial.println(" V");
  delay(100);
}
"""


def lesson13():
    L = Lesson(C, "13-arduino", "13. Arduino: pierwszy program")
    L.md("""
# Mikrokontroler

Do tej pory o tym, co robi obwód, decydowały połączenia. **Mikrokontroler** to mały komputer w jednym
układzie scalonym: ma procesor, pamięć i piny, którymi może sterować — a o tym, co robi, decyduje
**program**. Arduino Uno to płytka z mikrokontrolerem ATmega328P i wszystkim, czego potrzebuje, żeby
ruszyć.

Program dla Arduino (**szkic**) pisze się w języku C++. Ma dwie części: `setup()` wykonuje się raz,
a `loop()` w kółko. Szkic płytki otwierasz, zaznaczając ją i klikając **Szkic** w panelu po prawej —
przeglądarka sama go skompiluje, gdy uruchomisz symulację.
""")
    L.md("""
## Mruganie diodą

Klasyczny pierwszy program. Pin 13 jest **wyjściem**: `digitalWrite(13, HIGH)` daje na nim 5 V, `LOW` —
0 V. Opornik 220 Ω ogranicza prąd diody. Uruchom ⚡ i popatrz też na **monitor portu szeregowego** pod
schematem — tam trafia to, co program pisze przez `Serial.println`.
""")
    d = Drawing()
    d.add("ARD_1", "arduino", (0, 0), 0, None, BLINK)
    d.add("R_1", "resistor", (2, -2), 270, "220")
    d.add("LED_1", "led", (2, -6), 270, None, "red")
    d.connect(
        {
            "d13": [A("D13"), ("R_1", 0)],
            "GND": [A("GND"), ("LED_1", 1)],
        }
    )
    L.drawing("mruganie", d)
    L.md("""
## Wejścia: przycisk i potencjometr

Piny mogą też **czytać**. `digitalRead` mówi, czy na pinie jest 0, czy 5 V; `analogRead` mierzy napięcie
dokładnie (0–1023). A `analogWrite` udaje napięcie pośrednie: bardzo szybko włącza i wyłącza pin
(**PWM**), więc dioda świeci jaśniej lub ciemniej. Uruchom ⚡, przytrzymaj przycisk i przesuwaj suwak
potencjometru.
""")
    d = Drawing()
    d.add("ARD_1", "arduino", (0, 0), 0, None, INPUTS)
    d.add("B_1", "button", (14, -2), 270)
    d.add("R_1", "resistor", (6, -2), 270, "220")
    d.add("LED_1", "led", (6, -6), 270, None, "green")
    d.add("R_2", "resistor", (2, -2), 270, "220")
    d.add("LED_2", "led", (2, -6), 270, None, "red")
    d.add("P_1", "potentiometer", (8, 14), 0, "10k", "0.5")
    d.connect(
        {
            "d2": [A("D2"), ("B_1", 0)],
            "d9": [A("D9"), ("R_1", 0)],
            "d13": [A("D13"), ("R_2", 0)],
            "a0": [A("A0"), ("P_1", 2)],
            "5V": [A("5V"), ("P_1", 1)],
            "GND": [A("GND"), ("B_1", 1), ("LED_1", 1), ("LED_2", 1), ("P_1", 0)],
        }
    )
    L.drawing("wejscia", d)
    L.md("""
## Co dalej?

Znasz już podstawy: prąd, napięcie, opór, elementy i program. Kurs **Poznaj aplikację** pokazuje
wszystko, co można tu robić, a w folderze **Przykłady** czekają gry, Doom na Raspberry Pi Pico, radar,
theremin i kilkanaście innych projektów do rozebrania na części.
""")
    L.save()


if __name__ == "__main__":
    intro()
    for lesson in (
        lesson01,
        lesson02,
        lesson03,
        lesson04,
        lesson05,
        lesson06,
        lesson07,
        lesson08,
        lesson09,
        lesson10,
        lesson11,
        lesson12,
        lesson13,
    ):
        lesson()
