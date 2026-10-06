"""Kurs 2: poznaj aplikację — notatki, rysowanie, liczenie, symulacja, płytki, własne komponenty, zapis."""

from lib import A, Drawing, Lesson, Part, PartPin, course

C = "2-aplikacja"


def intro():
    course(
        C,
        "Poznaj aplikację",
        "Wszystko, co tu można robić: notatki z tekstem, wzorami i kodem, rysowanie schematów, liczenie "
        "obwodów krok po kroku, symulacja w czasie z oscyloskopem, Arduino i Raspberry Pi Pico w przeglądarce, "
        "własne komponenty i zapis na GitHubie.",
    )


def lesson01():
    L = Lesson(C, "01-notatki-i-komorki", "1. Notatki i komórki")
    L.md("""
# Notatka to ciąg komórek

Każda notatka składa się z **komórek** trzech rodzajów:

- **Tekst** — Markdown: nagłówki, pogrubienia, listy, tabele i wzory w LaTeX-u, jak ta komórka,
- **Kod** — Python z biblioteką `electro` do liczenia obwodów,
- **Schemat** — obwód narysowany na siatce, który można policzyć albo uruchomić w czasie.

Nową komórkę dodajesz przyciskami **Tekst**, **Kod** i **Schemat**, które pojawiają się pod komórką
i między komórkami, gdy najedziesz myszką. Komórkę przesuwasz, łapiąc za uchwyt z lewej (albo
strzałkami ↑ ↓), a usuwasz ikoną kosza — przez chwilę można to cofnąć. Tytuł notatki zmieniasz,
klikając go.
""")
    L.md("""
## Tekst

Kliknij tę komórkę dwa razy, żeby zobaczyć, jak jest napisana. Markdown to zwykły tekst z kilkoma
znakami:

- `# Nagłówek`, `## Mniejszy nagłówek` — nagłówki trafiają do **spisu treści** z lewej,
- `**pogrubienie**`, `*kursywa*`, `` `kod` ``,
- `- punkt listy`, `1. punkt numerowany`,
- wzór w linii: `$U = R \\cdot I$` daje $U = R \\cdot I$, a osobny, na środku, w podwójnych dolarach:

$$P = U \\cdot I = I^2 R = \\frac{U^2}{R}$$

| tabela | też | działa |
|---|:-:|--:|
| do lewej | środek | do prawej |
""")
    L.md("""
## Kod

Komórka z kodem to Python. Uruchamiasz ją przyciskiem ▶ albo **Shift+Enter**; wynik pojawia się pod
nią. Wszystkie komórki dzielą zmienne — to, co zdefiniujesz w jednej, widać w następnych. **Uruchom
wszystko** (w prawym górnym rogu) wykonuje całą notatkę od góry. Za pierwszym razem przeglądarka
ładuje Pythona — to chwila.
""")
    L.code("""
napiecie = 12
opor = 470
prad = napiecie / opor
print(f"I = {prad * 1000:.1f} mA")
""")
    L.code("""
# ta komórka widzi zmienne z poprzedniej
moc = napiecie * prad
round(moc, 3)
""")
    L.md("""
## Schemat

Schemat ma **nazwę** (na pasku nad nim) — i pod tą nazwą jest zmienną w kodzie. Ten nazywa się
`przyklad`:
""")
    d = Drawing()
    d.add("E_1", "voltage_source", (0, 6), 270, "12")
    d.add("R_1", "resistor", (2, 0), 0, "470")
    d.add("LED_1", "led", (10, 0), 90, None, "green")
    d.wire((0, 2), (0, 0), (2, 0))
    d.wire((6, 0), (10, 0))
    d.wire((10, 4), (10, 6), (0, 6))
    d.ground((0, 6))
    L.drawing("przyklad", d)
    L.code("""
wynik = przyklad.simulate(until=0.01)
print("prąd diody:", round(wynik.at("I_LED_1", 0.01) * 1000, 1), "mA")
""")
    L.md("""
## Spis treści i PDF

Ikona w lewym górnym rogu otwiera **spis treści**: nagłówki i schematy notatki. Przeciągając nagłówek,
przenosisz całą sekcję pod nim. Menu **⋯** w prawym górnym rogu ma **Eksport do PDF** (⌘P / Ctrl+P):
notatka składa się w porządny dokument — z motywem do wyboru, schematami i wzorami. Tam też jest wybór
symboli: europejskie (IEC — opornik to prostokąt) albo amerykańskie (IEEE — zygzak).
""")
    L.save()


def lesson02():
    L = Lesson(C, "02-rysowanie-schematow", "2. Rysowanie schematów")
    L.md("""
# Rysowanie schematów

Kliknij schemat, żeby zaczął reagować na klawisze. Na górze jest pasek **narzędzi**:

| narzędzie | klawisz | co robi |
|---|:-:|---|
| Zaznacz | V | zaznacza i przesuwa elementy i przewody |
| Rączka | H | przesuwa widok (albo przeciągnij tło, albo spacja) |
| Przewód | W | klik — początek, kolejne kliki — załamania, klik w zacisk — koniec |
| Elementy | K lub / | panel wszystkich elementów z wyszukiwarką |
| elementy z paska | 1–0 | opornik, źródło, masa… — pierwsze z biblioteki |

Zaznaczony element: **R** obraca go o 90° (dwa razy — odwraca, np. biegunowość źródła), **Del** usuwa,
**⌘C / ⌘V** kopiuje i wkleja pod kursorem. **Shift + klik** albo **Shift + przeciąganie** zaznacza wiele
naraz. **⌘Z** cofa, **F** włącza pełny ekran. Ikona **?** w rogu schematu przypomina wszystkie skróty.
""")
    L.md("""
## Jak łączą się przewody

- Przewody łączą się tylko **końcami** — z zaciskiem albo z innym przewodem (nawet w połowie jego
  długości, tworząc rozgałęzienie „T”, które widać jako kropkę).
- Przewód, który tylko **przechodzi** nad zaciskiem albo krzyżuje inny przewód, **nie łączy się** z nim.
- **Czerwona kropka** to zacisk, do którego nic nie jest podłączone.
- **Etykieta** (z biblioteki, sekcja Połączenia) nazywa węzeł: dwie etykiety o tej samej nazwie są
  połączone, choć nie ma między nimi przewodu. **Masa** to specjalna etykieta: punkt 0 V.

## Ćwiczenie: dokończ obwód

Elementy już stoją, brakuje przewodów. Połącz baterię, opornik i diodę w pętlę (narzędzie **Przewód**,
klawisz W), a potem sprawdź, czy dioda świeci (⚡). Czerwone kropki znikną, gdy wszystko będzie
podłączone.
""")
    d = Drawing()
    d.add("E_1", "voltage_source", (0, 6), 270, "9")
    d.add("R_1", "resistor", (4, 0), 0, "330")
    d.add("LED_1", "led", (14, 1), 90, None, "red")
    d.ground((0, 6))
    L.drawing("do_dokonczenia", d, exercise=True)
    L.md("""
## Wartości

Zaznacz element, a z prawej pojawi się jego **panel**: nazwa (np. `R_1`), wartość i to, co jeszcze da się
ustawić (kolor diody, częstotliwość źródła…). Wartość wpisujesz z przedrostkiem — `4.7k`, `100n`, `2m`;
**pusta** wartość znaczy „nie wiem” (solver jej szuka), a **litera** — symbol, z którym wynik wyjdzie
jako wzór.

## Schemat jako kod

Pasek nad schematem ma kartę **Kod**: to ten sam obwód zapisany w Pythonie. Zmień w nim wartość
i wróć do schematu — rysunek się zaktualizuje. Elementy dodaje się na rysunku, a w kodzie zmienia
tylko wartości.
""")
    L.save()


def lesson03():
    L = Lesson(C, "03-liczenie-na-papierze", "3. Liczenie na papierze")
    L.md("""
# Liczenie na papierze

Obwód z opornikami, źródłami, kondensatorami i cewkami (bez diod i tranzystorów) jest **liniowy** —
da się go policzyć dokładnie, tak jak na kartce. Robi to przycisk ▶ **Policz** nad schematem (albo
Shift+Enter): przy każdym elemencie pojawia się napięcie i prąd, a pod schematem — tabela wyników.
Strzałka przy prądzie pokazuje, w którą stronę naprawdę płynie.

Gdy zmienisz coś na schemacie, wyniki robią się szare: są nieaktualne, dopóki nie klikniesz ▶ znowu.
""")
    L.md("""
## Niewiadome i dane

Tu jest mostek Wheatstone'a: $R_x$ ma pustą wartość, a amperomierz pokazuje zero — mostek jest
w równowadze. To wystarczy, żeby wyznaczyć $R_x$: kliknij ▶.
""")
    d = Drawing()
    d.add("E_1", "voltage_source", (0, 14), 270, "10")
    d.add("R_1", "resistor", (8, 0), 90, "100")
    d.add("R_x", "resistor", (8, 6), 90)
    d.add("R_3", "resistor", (18, 0), 90, "50")
    d.add("R_4", "resistor", (18, 6), 90, "100")
    d.add("A_1", "ammeter", (11, 5), 0, "0")
    d.wire((0, 10), (0, 0), (8, 0))
    d.wire((8, 0), (18, 0))
    d.wire((8, 4), (8, 6))
    d.wire((18, 4), (18, 6))
    d.wire((8, 5), (11, 5))
    d.wire((15, 5), (18, 5))
    d.wire((8, 10), (8, 14))
    d.wire((18, 10), (18, 14))
    d.wire((0, 14), (18, 14))
    d.ground((0, 14))
    L.drawing("mostek", d, solve=True)
    L.md("""
## Kiedy danych brakuje

Jeśli niewiadomych jest więcej niż danych, solver nie zgaduje — policzy, co się da, a w rogu schematu
pojawi się ostrzeżenie. Kliknij je: dowiesz się, czego nie da się wyznaczyć, ilu danych brakuje
i **które pomiary by wystarczyły**. Tu nieznane są oba oporniki, a znany jest tylko prąd:
""")
    d = Drawing()
    d.add("E_1", "voltage_source", (0, 6), 270, "12")
    d.add("A_1", "ammeter", (2, 0), 0, "0.5")
    d.add("R_1", "resistor", (8, 0), 0)
    d.add("R_2", "resistor", (14, 0), 90)
    d.wire((0, 2), (0, 0), (2, 0))
    d.wire((6, 0), (8, 0))
    d.wire((12, 0), (14, 0))
    d.wire((14, 4), (14, 6), (0, 6))
    d.ground((0, 6))
    L.drawing("za_malo_danych", d, solve=True)
    L.md("""
Dostaw woltomierz równolegle do $R_2$ (z biblioteki: **Mierniki**) i wpisz w nim odczyt, np. `8`. Po ▶
oba opory są już znane.

## Krok po kroku

W komórce z kodem `steps(...)` pokazuje całe rozwiązanie: dane, każdy krok z wzorem i uzasadnieniem
(prawo Ohma, prawa Kirchhoffa…) i odpowiedź na to, czego szukamy (na schemacie: wartości zostawione
puste i wielkości z listy **Szukane**).
""")
    L.code("""
steps(mostek.final())
""")
    L.md("""
## Wzory zamiast liczb

Wartość może być literą. Wtedy wynik jest wzorem — dobrze to sprawdza rozwiązania z zeszytu:
""")
    L.code("""
E, R_1, R_2, R_3 = VoltageSource("E"), Resistor("R_1"), Resistor("R_2"), Resistor("R_3")
uklad = ~(E >> R_1 >> (R_2 | R_3))
uklad.final({E: "E", R_1: "R_1", R_2: "R_2", R_3: "R_3"})(I(R_1))
""")
    L.save()


def lesson04():
    L = Lesson(C, "04-symulacja-w-czasie", "4. Symulacja w czasie")
    L.md("""
# Symulacja w czasie

Diody, tranzystory, układy scalone i płytki nie są liniowe — takie obwody liczy się **w czasie**, krok po
kroku, jak w prawdziwym symulatorze. Przycisk ⚡ przy schemacie uruchamia obwód w czasie:

- **przewody** mają kolor napięcia (zielony — dodatnie, czerwony — ujemne, szary — zero),
- **diody i żarówki** świecą, **silniki** się kręcą, **buzzery** grają (jest przycisk wyciszenia),
- **łączniki** przełączasz kliknięciem, **przyciski** działają, dopóki je trzymasz,
- **potencjometr** i **czujniki** mają suwaki (kliknij element albo otwórz zakładkę **Regulacja**).

Pod schematem jest pasek: pauza, **tempo** (ile sekund obwodu na sekundę zegara — zwolnij, żeby
zobaczyć szybkie zjawiska) i zatrzymanie. Obwody liniowe też można uruchomić w czasie: mają przycisk
symulacji na dole schematu.
""")
    L.md("""
## Oscyloskop i miernik

Uruchom poniższy obwód. W panelu pod schematem zakładka **Wykres** to oscyloskop: **Dodaj przebieg…**
i wybierz napięcie węzła albo napięcie czy prąd elementu. Narzędzie **Miernik** (na pasku narzędzi
symulacji) pokazuje wszystko o elemencie albo przewodzie, który klikniesz — z wykresem.

Obwód to filtr RC: generator prostokąta 20 Hz ładuje kondensator przez opornik. Porównaj `V_we`
(prostokąt) z `V_wy` (zaokrąglone zbocza). Zmień $R_1$ na 10 kΩ — zbocza się rozciągną.
""")
    d = Drawing()
    d.add("E_1", "square_source", (0, 8), 270, "5", "20")
    d.add("R_1", "resistor", (2, 0), 0, "1k")
    d.add("C_1", "capacitor", (10, 4), 90, "4.7u")
    d.wire((0, 4), (0, 0), (2, 0))
    d.wire((6, 0), (10, 0))
    d.wire((10, 0), (10, 4))
    d.wire((10, 8), (0, 8))
    d.ground((0, 8))
    d.label("we", (0, 4))
    d.label("wy", (10, 0))
    L.drawing("filtr_rc", d)
    L.md("""
## Przyciski z klawiatury

Przyciskowi można przypisać **klawisz** (w jego panelu, w czasie gdy symulacja nie działa). Wtedy
kliknij schemat i steruj z klawiatury — tak grają gry w przykładach. Tu przycisk ma klawisz **spacja**,
a dioda zapala się, dopóki go trzymasz.
""")
    d = Drawing()
    d.add("E_1", "voltage_source", (0, 6), 270, "5")
    d.add("B_1", "button", (2, 0), 0, None, "Space")
    d.add("R_1", "resistor", (8, 0), 0, "220")
    d.add("LED_1", "led", (14, 0), 90, None, "blue")
    d.wire((0, 2), (0, 0), (2, 0))
    d.wire((6, 0), (8, 0))
    d.wire((12, 0), (14, 0))
    d.wire((14, 4), (14, 6), (0, 6))
    d.ground((0, 6))
    L.drawing("spacja", d)
    L.md("""
## Symulacja w kodzie

To samo da się zrobić w komórce z kodem: `schemat.simulate(until=...)` liczy przebiegi, a `plot(...)` je
rysuje. Wejścia (łączniki, przyciski, suwaki) podajesz w `inputs` — liczbą albo funkcją czasu:
""")
    L.code("""
przebieg = filtr_rc.simulate(until=0.1)
plot(przebieg, "V_we", "V_wy")
""")
    L.code("""
wcisniety = lambda t: 1 if 0.02 < t < 0.06 else 0
plot(spacja.simulate(until=0.08, inputs={"B_1_closed": wcisniety}), "I_LED_1")
""")
    L.save()


LCD_SKETCH = """// Licznik i napięcie z potencjometru na wyświetlaczu LCD z konwerterem I²C (adres 0x27).
#include <LiquidCrystal_I2C.h>

LiquidCrystal_I2C lcd(0x27, 16, 2);

void setup() {
  lcd.init();
  lcd.backlight();
  lcd.print("Czesc!");
  Serial.begin(9600);
}

void loop() {
  static unsigned long start = millis();
  float u = analogRead(A0) * 5.0 / 1023;
  lcd.setCursor(0, 1);
  lcd.print("A0=");
  lcd.print(u, 2);
  lcd.print("V t=");
  lcd.print((millis() - start) / 1000);
  lcd.print("s  ");
  Serial.println(u);
  delay(200);
}
"""


def lesson05():
    L = Lesson(C, "05-arduino-i-pico", "5. Arduino i Pico w przeglądarce")
    L.md("""
# Płytki: Arduino Uno i Raspberry Pi Pico

Na schemacie mogą stać prawdziwe płytki z mikrokontrolerami. Każda ma swój **szkic** — program w C++
(Arduino). Zaznacz płytkę i kliknij **Szkic** w jej panelu (albo kartę szkicu nad schematem): edytor
otworzy się obok rysunku. Po ⚡ przeglądarka **kompiluje** szkic (pierwszy raz pobiera kompilator,
potem to sekunda) i uruchamia go na emulowanym procesorze — tym samym kodzie maszynowym, który
dostałby prawdziwy układ.

- **Arduino Uno** — ATmega328P, 16 MHz, logika 5 V, piny D0–D13 i A0–A5,
- **Raspberry Pi Pico** — RP2040, dwa rdzenie 133 MHz, logika **3,3 V**, piny GP0–GP28.

Dostępne biblioteki: `Servo`, `LiquidCrystal`, `LiquidCrystal_I2C`, `Wire`, `SPI`, `EEPROM`,
`Adafruit_SSD1306` (z `Adafruit_GFX`), `RTClib`, a na Pico także `Adafruit_ILI9341`.

## Monitor portu szeregowego

To, co szkic wypisze przez `Serial.print`, pojawia się w zakładce **Konsola** pod schematem. Można tam
też pisać — szkic odczyta to przez `Serial.read()`. Błędy kompilacji pokazują się w tym samym miejscu,
z numerem linii.
""")
    L.md("""
## Przykład: LCD na I²C

Wyświetlacz z konwerterem I²C potrzebuje tylko czterech przewodów: zasilanie, masa, SDA (A4) i SCL (A5).
Uruchom ⚡ i kręć potencjometrem.
""")
    d = Drawing()
    d.add("ARD_1", "arduino", (0, 0), 0, None, LCD_SKETCH)
    d.add("LCD_1", "lcd1602_i2c", (26, 10), 0, None, "0x27")
    d.add("P_1", "potentiometer", (8, 14), 0, "10k", "0.5")
    d.connect(
        {
            "SDA": [A("A4"), ("LCD_1", 2)],
            "SCL": [A("A5"), ("LCD_1", 3)],
            "5V": [A("5V"), ("LCD_1", 1), ("P_1", 1)],
            "a0": [A("A0"), ("P_1", 2)],
            "GND": [A("GND"), ("LCD_1", 0), ("P_1", 0)],
        }
    )
    L.drawing("lcd", d)
    L.md("""
## Programy z plików

Pico może też dostać gotowy program: plik **.uf2** albo **.bin**, jak prawdziwe Pico przeciągane na dysk
USB. Zaznacz płytkę i kliknij **Wgraj plik .uf2 / .bin** albo po prostu upuść plik na płytkę. Tak
uruchamia się Doom w folderze Przykłady.

## Gdy komputer nie nadąża

Emulacja procesora to dużo liczenia. Gdy przeglądarka nie nadąża, Pico zwalnia — przy płytce widać
wtedy jego obecne taktowanie (np. **PICO_1 · 80 MHz**). Program działa tak samo, tylko wolniej.
""")
    L.save()


def switch_part() -> Part:
    """One's own component: a transistor switch — IN drives a load between the supply and OUT."""
    inner = Drawing()
    inner.add("R_1", "resistor", (2, 2), 0, "1k")
    inner.add("R_2", "resistor", (7, 3), 90, "10k")
    inner.add("Q_1", "npn", (9, 2), 0)
    inner.add("p1", "port", (2, 2), 0, None, "IN")
    inner.add("p2", "port", (12, -2), 0, None, "OUT")
    inner.add("p3", "port", (12, 9), 0, None, "GND")
    inner.wire((6, 2), (7, 2))
    inner.wire((7, 2), (9, 2))
    inner.wire((7, 2), (7, 3))
    inner.wire((12, 0), (12, -2))
    inner.wire((12, 4), (12, 9))
    inner.wire((7, 7), (7, 9), (12, 9))
    return Part(
        "Klucz",
        (4, 4),
        [PartPin("IN", "left", 2), PartPin("OUT", "top", 2), PartPin("GND", "bottom", 2)],
        inner,
    )


def lesson06():
    L = Lesson(C, "06-wlasne-komponenty", "6. Własne komponenty")
    L.md("""
# Własne komponenty

Kiedy jakiś kawałek obwodu powtarza się w wielu miejscach — klucz tranzystorowy, filtr, dzielnik,
wzmacniacz — możesz zamknąć go w **pudełku**: własnym komponencie z nazwą, obrysem i pinami. Potem
wstawiasz go na dowolny schemat, w dowolnej notatce, i łączysz przewodami jak każdy inny element.

## Jak zrobić komponent

1. Narysuj środek komponentu na zwykłym schemacie.
2. W miejscach, którymi komponent ma się łączyć z resztą obwodu, postaw element **Wyprowadzenie**
   (biblioteka elementów → **Połączenia**) i nadaj mu nazwę — np. `IN`, `OUT`, `GND`.
3. Kliknij ikonę układu scalonego na pasku nad schematem: **Zapisz jako komponent**. Wybierz nazwę,
   a dla każdego pinu stronę obrysu i kolejność; podgląd pokazuje, jak będzie wyglądał.
4. Gotowe: komponent jest w bibliotece elementów, w sekcji **Moje komponenty**, na każdym schemacie.
""")
    L.md("""
## Ćwiczenie: zapisz klucz tranzystorowy

Poniżej jest klucz z lekcji o tranzystorach — już z trzema wyprowadzeniami: `IN` (sterowanie), `OUT`
(tam podłącza się obciążenie) i `GND`. Kliknij **Zapisz jako komponent**, nazwij go „Klucz” i zapisz.
""")
    inner = switch_part().schematic
    d = Drawing()
    d.elements = list(inner.elements)
    d.wires = list(inner.wires)
    L.drawing("klucz_srodek", d, exercise=True)
    L.md("""
## Komponent na schemacie

Tak wygląda gotowy komponent, wstawiony dwa razy: każdy klucz steruje swoją diodą, a sterują nimi dwa
generatory o różnej częstotliwości. Uruchom ⚡ — symulacja „otwiera” pudełka i liczy wszystko, co jest
w środku. W kodzie elementy ze środka mają nazwy z przedrostkiem: tranzystor pierwszego klucza to
`U_1_Q_1`.
""")
    d = Drawing()
    d.parts["klucz"] = switch_part()
    d.add("E_1", "voltage_source", (0, 12), 270, "5")
    d.add("E_2", "square_source", (6, 16), 270, "5", "1")
    d.add("E_3", "square_source", (20, 16), 270, "5", "3")
    d.add("U_1", "part", (10, 6), 0, None, "klucz")
    d.add("U_2", "part", (24, 6), 0, None, "klucz")
    d.add("R_1", "resistor", (12, -6), 90, "220")
    d.add("LED_1", "led", (12, -2), 90, None, "red")
    d.add("R_2", "resistor", (26, -6), 90, "220")
    d.add("LED_2", "led", (26, -2), 90, None, "green")
    d.connect(
        {
            "5V": [("E_1", 1), ("R_1", 0), ("R_2", 0)],
            "a": [("R_1", 1), ("LED_1", 0)],
            "b": [("R_2", 1), ("LED_2", 0)],
            "o1": [("LED_1", 1), ("U_1", 1)],
            "o2": [("LED_2", 1), ("U_2", 1)],
            "i1": [("E_2", 1), ("U_1", 0)],
            "i2": [("E_3", 1), ("U_2", 0)],
            "GND": [("E_1", 0), ("E_2", 0), ("E_3", 0), ("U_1", 2), ("U_2", 2)],
        }
    )
    d.ground(d.pin("E_1", 0))
    L.drawing("dwa_klucze", d)
    L.code("""
p = dwa_klucze.simulate(until=2)
plot(p, "I_U_1_Q_1_c", "I_U_2_Q_1_c")
""")
    L.md("""
## Dobrze wiedzieć

- Komponent wstawiony na schemat to **kopia**: notatka zawiera wszystko, co potrzebne, i działa także
  u kogoś, kto takiego komponentu nie ma w swojej bibliotece.
- Zapisanie komponentu **pod tą samą nazwą** zastępuje go w bibliotece; schematy, na których już stoi,
  zmienią się dopiero, gdy wstawisz go na nie ponownie.
- W środku komponentu nie może być płytki (Arduino, Pico) — jej program nie ruszyłby w zamkniętym
  pudełku. Diody w środku świecą „niewidocznie”: symulacja je liczy, ale ich nie widać.
- Komponent może zawierać inne komponenty.
- Własne komponenty zapisują się razem z notatkami (także na GitHubie, jeśli jest połączony).
""")
    L.save()


def lesson07():
    L = Lesson(C, "07-zapisywanie-i-github", "7. Zapisywanie i GitHub")
    L.md("""
# Gdzie są moje notatki?

Notatki są **w tej przeglądarce** — w małym repozytorium git, które aplikacja prowadzi sama. Każda
zmiana zapisuje się od razu, bez klikania, i przetrwa zamknięcie karty i restart komputera. Nic nie
wychodzi do internetu, dopóki sam tego nie zechcesz.

## Przycisk zapisu

Ikona dyskietki w prawym górnym rogu (albo **⌘S / Ctrl+S**) zamyka **sesję**: wszystkie zmiany od
ostatniego zapisu stają się jednym wpisem w historii notatek. Kropka na przycisku znaczy, że są zmiany
jeszcze niezapisane w historii. Sesja zapisuje się też sama: po pół godzinie bez zmian i przy następnym
otwarciu aplikacji.

## GitHub

Jeśli chcesz mieć notatki także na innym komputerze — albo po prostu kopię w bezpiecznym miejscu — połącz
GitHuba: menu **⋯** → **Połącz z GitHubem**. Aplikacja założy Ci prywatne repozytorium `electro-notes`
i od tej pory:

- w trakcie pracy zmiany co chwilę lądują na GitHubie na osobnej gałęzi (bezpieczne, choć jeszcze nie
  w historii),
- zapis (⌘S) wysyła całą sesję jako jeden commit na gałąź `main`,
- przy otwarciu aplikacji pobiera to, co zmieniłeś na innym komputerze.

Gdy ta sama notatka zmieniła się w dwóch miejscach naraz, nic nie przepada: zostaje Twoja wersja,
a obok pojawia się kopia z dopiskiem **(z GitHuba)**.

## Pliki

Każda notatka to jeden plik `.electro.json` (w repozytorium na GitHubie — w folderze `notes`). Taki plik
otworzysz na stronie głównej przyciskiem **Otwórz plik**: stanie się nową notatką.

## Kursy i przykłady

Lekcję z kursu możesz od razu zmieniać i uruchamiać, ale nic się w niej nie zapisuje — do Twoich
notatek trafi dopiero, gdy klikniesz **Dodaj do moich notatek** na dole strony. Przycisk **Dodaj cały
kurs do notatek** na stronie kursu kopiuje wszystkie lekcje naraz, do nowego folderu.
""")
    L.save()


if __name__ == "__main__":
    intro()
    for lesson in (lesson01, lesson02, lesson03, lesson04, lesson05, lesson06, lesson07):
        lesson()
