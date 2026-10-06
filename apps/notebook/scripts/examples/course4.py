"""Przykłady: gry, Doom, instrumenty, czujniki, analogowe klasyki — każdy do uruchomienia i rozebrania."""

from pathlib import Path

from lib import PI, A, Drawing, Lesson, course, sketch

C = "4-przyklady"
FIXTURES = Path(__file__).parents[2] / "src/features/simulation/fixtures"


def intro():
    course(
        C,
        "Przykłady",
        "Ponad dwadzieścia projektów do uruchomienia i rozebrania na części: prawdziwy Doom na Raspberry Pi Pico, "
        "Tetris, wąż, Pong i Flappy Bird, gra w życie i fraktal Mandelbrota, Simon, theremin, radar, "
        "oscyloskop, mostek H do silnika i analogowe klasyki — multiwibrator i wzmacniacz tranzystorowy.",
    )


# ------------------------------------------------------------------ helpers


def oled(d: Drawing, at=(4, -14), id="OLED_1"):
    d.add(id, "ssd1306", at, 0, None, "0x3C")
    return {"GND": (id, 0), "VCC": (id, 1), "SCL": (id, 2), "SDA": (id, 3)}


def lcd_i2c(d: Drawing, at, id="LCD_1"):
    d.add(id, "lcd1602_i2c", at, 0, None, "0x27")
    return {"GND": (id, 0), "VCC": (id, 1), "SDA": (id, 2), "SCL": (id, 3)}


def tft(d: Drawing, at=(16, 6), id="TFT_1"):
    d.add(id, "ili9341", at, 0)
    d.add(f"t_{id}", "terminal", d.pin(id, 8), 0)  # MISO: the display is only written to
    return {n: (id, k) for k, n in enumerate(["3V3", "GND", "cs", "rst", "dc", "mosi", "sck", "bl"])}


def tft_nets(t):
    return {
        "cs": [PI("GP17"), t["cs"]],
        "rst": [PI("GP21"), t["rst"]],
        "dc": [PI("GP20"), t["dc"]],
        "mosi": [PI("GP19"), t["mosi"]],
        "sck": [PI("GP18"), t["sck"]],
        "bl": [PI("GP22"), t["bl"]],
    }


def sonar(d: Drawing, at, id="US_1", distance="40"):
    d.add(id, "ultrasonic", at, 0, None, distance)
    return {"VCC": (id, 0), "TRIG": (id, 1), "ECHO": (id, 2), "GND": (id, 3)}


def led(d: Drawing, k: int, x: int, y: int, color: str):
    """A resistor and an LED standing up from (x, y): the resistor's lower pin at (x, y), the LED's
    cathode on top at (x, y - 8), for the ground net."""
    d.add(f"R_{k}", "resistor", (x, y), 270, "220")
    d.add(f"LED_{k}", "led", (x, y - 4), 270, None, color)
    return (f"R_{k}", 0), (f"LED_{k}", 1)


# ------------------------------------------------------------------ Pico: Doom, a shooter, Tetris, Mandelbrot

DOOM_TEXT = """
# DOOM na Raspberry Pi Pico

Tak, ten Doom: shareware'owy DOOM1.WAD z 1993 roku, epizod pierwszy, na emulowanym Raspberry Pi Pico
(RP2040: dwa rdzenie Cortex-M0+, 264 KB RAM) z kolorowym wyświetlaczem **TFT 320×240** na SPI
(ILI9341: SCK GP18, MOSI GP19, CS GP17, DC GP20, RESET GP21, podświetlenie GP22) i ośmioma przyciskami.

Obwód jest gotowy — brakuje programu. Doom to nie szkic, tylko gotowy obraz pamięci flash, taki jak
plik UF2 przeciągany na prawdziwe Pico:

1. **Pobierz go**: [doom.bin](https://github.com/geraldserafin/electro-doom/releases/download/doom/doom.bin)
   z [geraldserafin/electro-doom](https://github.com/geraldserafin/electro-doom). Tam jest też skrypt, który
   zbuduje go od zera: port [kilograham/rp2040-doom](https://github.com/kilograham/rp2040-doom), wyświetlacz
   z [pondahai/rp2040-doom-ili9341](https://github.com/pondahai/rp2040-doom-ili9341) i mała łatka pod
   emulator (bez dźwięku, klatki przez DMA).
2. **Wgraj go**: zaznacz płytkę i kliknij **Wgraj plik .uf2 / .bin** — albo po prostu upuść plik na płytkę.
   Plik zapisze się razem z notatkami, a pierwsza linia programu płytki będzie na niego wskazywać.
3. Uruchom symulację (⚡). Po chwili ekran tytułowy i demo; **kliknij schemat** i graj z klawiatury:
   **Enter** — menu i wybór (New Game), **strzałki** — ruch, **Ctrl** — strzał, **spacja** — drzwi,
   **Esc** — menu.

Gdy komputer nie nadąża, rdzenie zwalniają — o ile, widać przy płytce (np. **PICO_1 · 150 MHz**).
"""

DOOM_SKETCH = """// Tu przyjdzie Doom: pobierz doom.bin (github.com/geraldserafin/electro-doom, Releases) i wgraj go —
// zaznacz płytkę → „Wgraj plik .uf2 / .bin” albo upuść plik na płytkę. Ten szkic zostanie pod linią z plikiem.
// TFT: SCK GP18, MOSI GP19, CS GP17, DC GP20, RESET GP21, podświetlenie GP22.
// Przyciski do GND: ↑ GP9, ↓ GP5, ← GP8, → GP6, strzał GP3, użyj GP2, Enter GP4, menu GP28.

void setup() {}

void loop() {}
"""


def doom():
    L = Lesson(C, "01-doom", "DOOM na Raspberry Pi Pico")
    L.md(DOOM_TEXT)
    d = Drawing()
    d.add("PICO_1", "pico", (0, 0), 0, None, DOOM_SKETCH)
    t = tft(d)
    keys = {
        "GP9": "ArrowUp",
        "GP5": "ArrowDown",
        "GP8": "ArrowLeft",
        "GP6": "ArrowRight",
        "GP3": "Control",
        "GP2": "Space",
        "GP4": "Enter",
        "GP28": "Escape",
    }
    for k, key in enumerate(keys.values()):
        d.add(f"B_{k + 1}", "button", (-4 - 3 * k, 19), 90, None, key)
    d.connect(
        {
            **tft_nets(t),
            **{f"key_{pin}": [PI(pin), (f"B_{k + 1}", 0)] for k, pin in enumerate(keys)},
            "3V3": [PI("3V3"), t["3V3"]],
            "GND": [PI("GND"), t["GND"], *[(f"B_{k + 1}", 1) for k in range(len(keys))]],
        }
    )
    L.drawing("doom", d)
    L.md("""
## Jak to możliwe?

Emulator wykonuje instrukcja po instrukcji ten sam kod maszynowy, który działałby na prawdziwym Pico,
razem z peryferiami: SPI z DMA wysyła klatki do wyświetlacza, a sterownik ILI9341 w przeglądarce
zamienia je na piksele. Doom renderuje świat metodą BSP (drzewa podziału przestrzeni) — w 1993 roku na
procesorze 386 było to objawienie, a tu działa na mikrokontrolerze za kilkanaście złotych.
""")
    L.save()


def shooter():
    L = Lesson(C, "02-strzelanka-oled", "Strzelanka 3D na OLED-zie")
    L.md("""
# Strzelanka 3D na ekranie 128×64

Zanim wgrasz prawdziwego Dooma — gra w jego duchu, napisana jako zwykły szkic: korytarze liczone
**rzucaniem promieni** (jak w Wolfensteinie 3D z 1992 roku), ściany cieniowane ditheringiem, demony
jako sprite'y za ścianami. Wszystko na monochromatycznym OLED-zie przez I²C (GP4 SDA, GP5 SCL), z buzzerem
na GP15.

**Jak grać:** kliknij schemat, żeby miał fokus, i sterują **strzałki**; **spacja** strzela i zaczyna grę.

**Rzucanie promieni:** dla każdej kolumny ekranu z oczu gracza wychodzi promień i kroczy po mapie
kratka po kratce (algorytm DDA), aż trafi w ścianę. Im dalej ściana, tym niższy jej pasek na ekranie —
i z samych takich pasków powstaje trójwymiarowy korytarz.
""")
    d = Drawing()
    d.add("PICO_1", "pico", (0, 0), 0, None, (FIXTURES / "hell.pico.ino").read_text())
    o = oled(d, (-14, -8))
    d.add("BZ_1", "passive_buzzer", (-6, 9), 0)
    keys = {"GP10": "ArrowUp", "GP11": "ArrowDown", "GP12": "ArrowLeft", "GP13": "ArrowRight", "GP14": "Space"}
    for k, key in enumerate(keys.values()):
        d.add(f"B_{k + 1}", "button", (-4 - 3 * k, 19), 90, None, key)
    d.connect(
        {
            "sda": [PI("GP4"), o["SDA"]],
            "scl": [PI("GP5"), o["SCL"]],
            "buzz": [PI("GP15"), ("BZ_1", 0)],
            **{f"key_{pin}": [PI(pin), (f"B_{k + 1}", 0)] for k, pin in enumerate(keys)},
            "3V3": [PI("3V3"), o["VCC"]],
            "GND": [PI("GND"), o["GND"], ("BZ_1", 1), *[(f"B_{k + 1}", 1) for k in range(len(keys))]],
        }
    )
    L.drawing("strzelanka", d)
    L.save()


def tetris():
    L = Lesson(C, "03-tetris", "Tetris na kolorowym wyświetlaczu")
    L.md("""
# Tetris

Klasyk Aleksieja Pażytnowa z 1984 roku na Raspberry Pi Pico z kolorowym TFT 240×320. Siedem klocków
(tetromino) w czterech obrotach każdy zapisanych jako 16-bitowe maski 4×4, plansza 10×20, punkty jak
w wersji z Game Boya.

**Jak grać:** kliknij schemat i użyj klawiatury: **← →** przesuwają, **↑** obraca, **↓** przyspiesza,
**spacja** zrzuca klocek na dół.

Dwa pomysły warte podejrzenia w szkicu:

- **rysowanie tylko zmian** — szkic pamięta, co jest na ekranie, i wysyła przez SPI tylko kratki, które
  się zmieniły; pełny ekran to 150 KB, a jedna kratka — 450 bajtów,
- **odbicie od ściany** (*wall kick*) — obrót przy krawędzi próbuje przesunąć klocek o kratkę albo dwie,
  zamiast po prostu odmówić.
""")
    d = Drawing()
    d.add("PICO_1", "pico", (0, 0), 0, None, sketch("tetris.pico.ino"))
    t = tft(d)
    keys = {"GP2": "ArrowLeft", "GP3": "ArrowRight", "GP4": "ArrowUp", "GP5": "ArrowDown", "GP6": "Space"}
    for k, key in enumerate(keys.values()):
        d.add(f"B_{k + 1}", "button", (-4 - 3 * k, 19), 90, None, key)
    d.connect(
        {
            **tft_nets(t),
            **{f"key_{pin}": [PI(pin), (f"B_{k + 1}", 0)] for k, pin in enumerate(keys)},
            "3V3": [PI("3V3"), t["3V3"]],
            "GND": [PI("GND"), t["GND"], *[(f"B_{k + 1}", 1) for k in range(len(keys))]],
        }
    )
    L.drawing("tetris", d)
    L.save()


def mandelbrot():
    L = Lesson(C, "04-mandelbrot", "Fraktal Mandelbrota")
    L.md("""
# Zbiór Mandelbrota

Najsłynniejszy obiekt matematyki eksperymentalnej. Weź liczbę zespoloną $c$ i powtarzaj
$z \\to z^2 + c$, zaczynając od $z = 0$. Dla jednych $c$ ciąg ucieka do nieskończoności, dla innych
zostaje blisko zera — te drugie tworzą zbiór Mandelbrota (czarny). Brzeg zbioru jest nieskończenie
skomplikowany: przybliżaj go, a zawsze znajdziesz nowe spirale, gałęzie i miniaturowe kopie całości.

Szkic liczy każdy piksel ekranu 320×240 i koloruje go według tego, jak szybko $z$ uciekło, a potem
przybliża obraz dwukrotnie, w stronę „Doliny Konika Morskiego”. Obraz powstaje wiersz po wierszu —
widać, ile to liczenia. Przycisk (klawisz **R**) wraca do początku.

**Stały przecinek:** RP2040 nie ma koprocesora do ułamków, więc szkic liczy na liczbach całkowitych,
w których $1 = 2^{24}$. Mnożenie dwóch takich liczb to zwykłe mnożenie i przesunięcie o 24 bity w prawo —
kilkanaście razy szybciej niż `float` liczony programowo.
""")
    d = Drawing()
    d.add("PICO_1", "pico", (0, 0), 0, None, sketch("mandelbrot.pico.ino"))
    t = tft(d)
    d.add("B_1", "button", (-4, 19), 90, None, "r")
    d.connect(
        {
            **tft_nets(t),
            "key": [PI("GP2"), ("B_1", 0)],
            "3V3": [PI("3V3"), t["3V3"]],
            "GND": [PI("GND"), t["GND"], ("B_1", 1)],
        }
    )
    L.drawing("mandelbrot", d)
    L.code("""
# ten sam zbiór w Pythonie, w małej rozdzielczości — znakami
for y in range(12, -13, -2):
    wiersz = ""
    for x in range(-40, 16):
        c, z, i = complex(x / 20, y / 10), 0, 0
        while abs(z) <= 2 and i < 30:
            z, i = z * z + c, i + 1
        wiersz += "#" if i == 30 else " .:-=+*%@"[min(i, 8)]
    print(wiersz)
""")
    L.save()


# ------------------------------------------------------------------ Arduino games on an OLED


def oled_game(name, title, text, sketch_name, keys: dict, extra=None):
    """An Uno, an OLED on I²C, buttons to ground (pin → key), a passive buzzer on D8."""
    L = Lesson(C, name, title)
    L.md(text)
    d = Drawing()
    d.add("ARD_1", "arduino", (0, 0), 0, None, sketch(sketch_name))
    o = oled(d, (22, -14))
    d.add("BZ_1", "passive_buzzer", (22, 4), 0)
    for k, key in enumerate(keys.values()):
        d.add(f"B_{k + 1}", "button", (15 - 3 * k, -6), 90, None, key)
    nets = {
        "sda": [A("A4"), o["SDA"]],
        "scl": [A("A5"), o["SCL"]],
        "buzz": [A("D8"), ("BZ_1", 0)],
        **{f"key_{pin}": [A(pin), (f"B_{k + 1}", 1)] for k, pin in enumerate(keys)},
        "5V": [A("5V"), o["VCC"]],
        "GND": [A("GND"), o["GND"], ("BZ_1", 1), *[(f"B_{k + 1}", 0) for k in range(len(keys))]],
    }
    if extra:
        extra(d, nets)
    d.connect(nets)
    L.drawing(name.split("-", 1)[1].replace("-", "_"), d)
    return L


def snake():
    L = oled_game(
        "05-waz",
        "Wąż",
        """
# Wąż

Gra z telefonów Nokii z 1997 roku: wąż pełznie po planszy, zjada jedzenie i rośnie, a gra kończy się, gdy
wjedzie w ścianę albo we własny ogon. Z każdym punktem jest szybciej.

**Jak grać:** uruchom ⚡, kliknij schemat i steruj **strzałkami**. Po końcu gry dowolny kierunek zaczyna
od nowa.

**Ciało węża** to dwie tablice współrzędnych: głowa pod indeksem 0, a przy każdym ruchu wszystko
przesuwa się o jedno miejsce dalej. Arduino Uno ma tylko 2 KB pamięci RAM, z czego 1 KB zajmuje obraz
OLED-a — dlatego wąż ma najwyżej 120 segmentów.
""",
        "snake.ino",
        {"D2": "ArrowUp", "D3": "ArrowDown", "D4": "ArrowLeft", "D5": "ArrowRight"},
    )
    L.save()


def pong():
    def pots(d, nets):
        d.add("P_1", "potentiometer", (8, 14), 0, "10k", "0.5")
        d.add("P_2", "potentiometer", (16, 14), 0, "10k", "0.5")
        nets["a0"] = [A("A0"), ("P_1", 2)]
        nets["a1"] = [A("A1"), ("P_2", 2)]
        nets["5V"] += [("P_1", 1), ("P_2", 1)]
        nets["GND"] += [("P_1", 0), ("P_2", 0)]

    L = oled_game(
        "06-pong",
        "Pong dla dwóch graczy",
        """
# Pong

Pierwsza gra wideo, która odniosła sukces (Atari, 1972): dwie paletki i piłka. Każdy gracz kręci swoim
**potencjometrem** — dokładnie tak sterowało się pierwszymi konsolami. Piłka przyspiesza po każdym
odbiciu, a im dalej od środka paletki trafi, tym bardziej ukośnie leci. Do siedmiu punktów.

**Jak grać:** uruchom ⚡ i przesuwaj suwaki potencjometrów $P_1$ (lewy gracz) i $P_2$ (prawy) — klikając
je albo w zakładce **Regulacja** pod schematem.
""",
        "pong.ino",
        {},
        pots,
    )
    L.save()


def flappy():
    L = oled_game(
        "07-flappy",
        "Flappy Bird",
        """
# Flappy

Jeden przycisk, grawitacja i rury. Każde naciśnięcie podrywa ptaka do góry, a potem spada coraz
szybciej — jak w prawdziwej fizyce: prędkość rośnie o stałą wartość w każdej klatce (przyspieszenie),
a wysokość zmienia się o prędkość.

**Jak grać:** uruchom ⚡, kliknij schemat i naciskaj **spację**.
""",
        "flappy.ino",
        {"D2": "Space"},
    )
    L.save()


def life():
    L = oled_game(
        "08-gra-w-zycie",
        "Gra w życie",
        """
# Gra w życie

Automat komórkowy Johna Conwaya (1970). Plansza z komórkami — żywymi albo martwymi — i dwie reguły:

- martwa komórka z dokładnie **trzema** żywymi sąsiadami ożywa,
- żywa komórka z **dwoma albo trzema** żywymi sąsiadami przeżywa; każda inna umiera.

Nic więcej — a z tych reguł wyrastają szybowce, które przemierzają planszę, oscylatory, „działa” strzelające
szybowcami, a nawet (na dużych planszach) cały komputer. Gra w życie jest równoważna maszynie Turinga.

Uruchom ⚡ i patrz. Przycisk (klawisz **R**) losuje nową planszę. Każda komórka to jeden bit, więc plansza
64×32 zajmuje tylko 256 bajtów.
""",
        "life.ino",
        {"D2": "r"},
    )
    L.save()


# ------------------------------------------------------------------ Arduino: games and toys with LEDs, displays


def simon():
    L = Lesson(C, "09-simon", "Simon: gra pamięciowa")
    L.md("""
# Simon

Elektroniczna gra z 1978 roku: cztery kolory, cztery dźwięki. Arduino pokazuje sekwencję, a Ty ją
powtarzasz. Z każdą rundą sekwencja jest o jeden kolor dłuższa — i szybsza. Poziom widać na monitorze
portu szeregowego (zakładka **Konsola**).

**Jak grać:** uruchom ⚡, kliknij schemat i naciskaj klawisze **1–4** (albo przytrzymuj przyciski myszką).
""")
    d = Drawing()
    d.add("ARD_1", "arduino", (0, 0), 0, None, sketch("simon.ino"))
    colors = ["green", "red", "yellow", "blue"]
    nets = {"GND": [A("GND")]}
    for k in range(4):
        r, cathode = led(d, k + 1, -2 - 3 * k, -2, colors[k])
        nets[f"led{k}"] = [A(f"D{8 + k}"), r]
        nets["GND"].append(cathode)
        d.add(f"B_{k + 1}", "button", (20 + 3 * k, -10), 90, None, str(k + 1))
        nets[f"key{k}"] = [A(f"D{2 + k}"), (f"B_{k + 1}", 1)]
        nets["GND"].append((f"B_{k + 1}", 0))
    d.add("BZ_1", "passive_buzzer", (22, 4), 0)
    nets["buzz"] = [A("D12"), ("BZ_1", 0)]
    nets["GND"].append(("BZ_1", 1))
    d.connect(nets)
    L.drawing("simon", d)
    L.save()


def reflex():
    L = Lesson(C, "10-refleks", "Tester refleksu")
    L.md("""
# Jak szybki jest Twój refleks?

Po losowej chwili zapala się dioda — naciśnij przycisk najszybciej, jak umiesz. Arduino mierzy czas
funkcją `millis()` (milisekundy od startu) i pokazuje wynik na wyświetlaczu LCD, razem z rekordem.
Naciśnięcie przed zapaleniem to falstart. Typowy czas reakcji człowieka na światło to 200–250 ms.

**Jak grać:** uruchom ⚡, kliknij schemat i naciskaj **spację**.
""")
    d = Drawing()
    d.add("ARD_1", "arduino", (0, 0), 0, None, sketch("reflex.ino"))
    r, cathode = led(d, 1, 6, -2, "red")
    d.add("B_1", "button", (14, -6), 90, None, "Space")
    d.add("BZ_1", "passive_buzzer", (22, -4), 0)
    lc = lcd_i2c(d, (26, 10))
    d.connect(
        {
            "led": [A("D9"), r],
            "key": [A("D2"), ("B_1", 1)],
            "buzz": [A("D8"), ("BZ_1", 0)],
            "SDA": [A("A4"), lc["SDA"]],
            "SCL": [A("A5"), lc["SCL"]],
            "5V": [A("5V"), lc["VCC"]],
            "GND": [A("GND"), cathode, ("B_1", 0), ("BZ_1", 1), lc["GND"]],
        }
    )
    L.drawing("refleks", d)
    L.save()


def theremin():
    L = Lesson(C, "11-theremin", "Theremin")
    L.md("""
# Theremin

Pierwszy elektroniczny instrument (Lew Termen, 1920) — gra się na nim, nie dotykając go: dłoń zbliżona
do anteny zmienia wysokość dźwięku. Tu antenę zastępuje ultradźwiękowy czujnik odległości HC-SR04,
a żeby łatwiej było trafić w melodię, dźwięk przeskakuje po nutach skali C-dur.

Uruchom ⚡ i przesuwaj suwak czujnika (odległość dłoni). Na **Konsoli** widać odległość i nutę.

**Jak działa HC-SR04:** impuls 10 µs na TRIG wysyła paczkę ultradźwięków 40 kHz; ECHO jest w stanie
wysokim tyle, ile dźwięk leciał tam i z powrotem — 58 µs na każdy centymetr odległości.
""")
    d = Drawing()
    d.add("ARD_1", "arduino", (0, 0), 0, None, sketch("theremin.ino"))
    s = sonar(d, (-12, -8), distance="30")
    d.add("BZ_1", "passive_buzzer", (20, -4), 0)
    d.connect(
        {
            "trig": [A("D9"), s["TRIG"]],
            "echo": [A("D10"), s["ECHO"]],
            "buzz": [A("D8"), ("BZ_1", 0)],
            "5V": [A("5V"), s["VCC"]],
            "GND": [A("GND"), s["GND"], ("BZ_1", 1)],
        }
    )
    L.drawing("theremin", d)
    L.save()


def parking():
    L = Lesson(C, "12-czujnik-parkowania", "Czujnik parkowania")
    L.md("""
# Czujnik parkowania

Jak w samochodzie: im bliżej przeszkody, tym szybciej pika i tym więcej diod się pali — dwie zielone,
dwie żółte i czerwona. Poniżej 10 cm dźwięk jest ciągły.

Uruchom ⚡ i przesuwaj przeszkodę suwakiem czujnika. Tu buzzer jest **aktywny** — ma własny generator
i piszczy, gdy tylko dostanie napięcie, więc szkic tylko go włącza i wyłącza.
""")
    d = Drawing()
    d.add("ARD_1", "arduino", (0, 0), 0, None, sketch("parking.ino"))
    s = sonar(d, (20, 14), distance="80")
    nets = {"GND": [A("GND"), s["GND"]]}
    for k, color in enumerate(["green", "green", "yellow", "yellow", "red"]):
        r, cathode = led(d, k + 1, -2 - 3 * k, -2, color)
        nets[f"led{k}"] = [A(f"D{3 + k}"), r]
        nets["GND"].append(cathode)
    d.add("BZ_1", "buzzer", (26, -10), 90)
    nets |= {
        "trig": [A("D9"), s["TRIG"]],
        "echo": [A("D10"), s["ECHO"]],
        "buzz": [A("D8"), ("BZ_1", 1)],
        "5V": [A("5V"), s["VCC"]],
    }
    nets["GND"].append(("BZ_1", 0))
    d.connect(nets)
    L.drawing("parkowanie", d)
    L.save()


def thermometer():
    L = Lesson(C, "13-termometr", "Termometr cyfrowy")
    L.md("""
# Termometr

Termistor NTC to opornik, którego opór spada, gdy robi się cieplej: 10 kΩ przy 25 °C, ok. 3,6 kΩ przy
50 °C. W dzielniku z opornikiem 10 kΩ zamienia temperaturę na napięcie, które mierzy Arduino. Z napięcia
liczy opór termistora, a z oporu temperaturę:

$$\\frac{1}{T} = \\frac{1}{T_0} + \\frac{1}{B} \\ln\\frac{R}{R_0}$$

($T$ w kelwinach, $T_0 = 298{,}15$ K, $R_0 = 10$ kΩ, $B = 3950$ K — z karty katalogowej termistora).

Uruchom ⚡ i zmieniaj temperaturę suwakiem termistora; LCD pokazuje też minimum i maksimum.
""")
    d = Drawing()
    d.add("ARD_1", "arduino", (0, 0), 0, None, sketch("thermometer.ino"))
    d.add("RT_1", "thermistor", (4, 14), 0, "10k", "22")
    d.add("R_1", "resistor", (12, 14), 0, "10k")
    lc = lcd_i2c(d, (26, 10))
    d.connect(
        {
            "a0": [A("A0"), ("RT_1", 1), ("R_1", 0)],
            "SDA": [A("A4"), lc["SDA"]],
            "SCL": [A("A5"), lc["SCL"]],
            "5V": [A("5V"), ("RT_1", 0), lc["VCC"]],
            "GND": [A("GND"), ("R_1", 1), lc["GND"]],
        }
    )
    L.drawing("termometr", d)
    L.code("""
import math
# ta sama zależność w Pythonie: temperatura → opór termistora → napięcie na A0
for t in [0, 10, 20, 25, 30, 40, 50]:
    r = 10_000 * math.exp(3950 * (1 / (t + 273.15) - 1 / 298.15))
    u = 5 * 10_000 / (r + 10_000)
    print(f"{t:>3} °C: R = {r / 1000:5.2f} kΩ, U_A0 = {u:.2f} V")
""")
    L.save()


def radar():
    L = Lesson(C, "14-radar", "Radar")
    L.md("""
# Radar

Serwo obraca czujnik odległości od 0° do 180° i z powrotem, a OLED rysuje ekran radaru: półokrąg ze
wskazówką i echami przeszkód. Kąt i odległość zamieniają się na punkt na ekranie przez sinus
i cosinus — współrzędne biegunowe na kartezjańskie.

Uruchom ⚡ i przesuwaj przeszkodę suwakiem czujnika w trakcie obrotu — echa przesuwają się bliżej
i dalej. (Symulowany czujnik widzi przeszkodę w każdym kierunku w tej samej odległości; w prawdziwym
świecie zobaczyłbyś kształt pokoju.)
""")
    d = Drawing()
    d.add("ARD_1", "arduino", (0, 0), 0, None, sketch("radar.ino"))
    o = oled(d, (26, 4))
    d.add("M_1", "servo", (4, -10), 0)
    s = sonar(d, (-12, -8), distance="60")
    d.connect(
        {
            "servo": [A("D9"), ("M_1", 0)],
            "trig": [A("D6"), s["TRIG"]],
            "echo": [A("D7"), s["ECHO"]],
            "sda": [A("A4"), o["SDA"]],
            "scl": [A("A5"), o["SCL"]],
            "5V": [A("5V"), ("M_1", 1), s["VCC"], o["VCC"]],
            "GND": [A("GND"), ("M_1", 2), s["GND"], o["GND"]],
        }
    )
    L.drawing("radar", d)
    L.save()


def dice():
    L = Lesson(C, "15-kostka", "Elektroniczna kostka do gry")
    L.md("""
# Kostka do gry

Naciśnij przycisk, a cyfry na wyświetlaczu zaczną się kręcić — coraz wolniej, aż kostka „stanie” na
wyniku od 1 do 6. Każdy segment wyświetlacza to osobna dioda z własnym opornikiem; cyfry są zapisane
jako maski bitowe (bit 0 — segment a, …, bit 6 — segment g).

**Skąd losowość?** Komputer liczy deterministycznie — `random()` daje ciąg liczb, który tylko wygląda na
losowy, i za każdym razem zaczynałby się tak samo. Dlatego szkic ustawia **ziarno** z chwili naciśnięcia,
zmierzonej w mikrosekundach: tego człowiek nie powtórzy.

**Jak grać:** uruchom ⚡, kliknij schemat i naciśnij **spację**.
""")
    d = Drawing()
    d.add("ARD_1", "arduino", (0, 0), 0, None, sketch("dice.ino"))
    d.add("DS_1", "seven_segment", (27, -22), 0)
    for i in range(7):
        d.add(f"R_{i + 1}", "resistor", (20 + 2 * i, -4), 270, "220")
    d.add("B_1", "button", (-2, -6), 90, None, "Space")
    d.add("BZ_1", "passive_buzzer", (22, 4), 0)
    d.connect(
        {f"to_{s}": [A(f"D{2 + i}"), (f"R_{i + 1}", 0)] for i, s in enumerate("abcdefg")}
        | {f"seg_{s}": [(f"R_{i + 1}", 1), ("DS_1", i)] for i, s in enumerate("abcdefg")}
        | {
            "key": [A("D12"), ("B_1", 1)],
            "buzz": [A("D9"), ("BZ_1", 0)],
            "GND": [A("GND"), ("DS_1", 8), ("B_1", 0), ("BZ_1", 1)],
        }
    )
    d.add("t1", "terminal", d.pin("DS_1", 7), 0)
    L.drawing("kostka", d)
    L.save()


def melody():
    L = Lesson(C, "16-melodia", "Melodia z Tetrisa")
    L.md("""
# Korobeiniki

Rosyjska piosenka ludowa z XIX wieku, którą cały świat zna z Tetrisa na Game Boya. Melodia to tablica
par: częstotliwość nuty i jej długość w ósemkach. `tone()` gra dźwięk o danej częstotliwości na
buzzerze pasywnym, a dioda RGB zmienia kolor z wysokością nuty. Potencjometr ustawia tempo.

**Skąd częstotliwości?** Nuta A4 to 440 Hz, a każdy półton wyżej mnoży częstotliwość przez
$\\sqrt[12]{2} \\approx 1{,}0595$ — po dwunastu półtonach (oktawa) wychodzi dokładnie dwa razy więcej.
""")
    d = Drawing()
    d.add("ARD_1", "arduino", (0, 0), 0, None, sketch("melody.ino"))
    d.add("BZ_1", "passive_buzzer", (0, -6), 0)
    for k in range(3):
        d.add(f"R_{k + 1}", "resistor", (20, -6 + 2 * k), 0, "220")
    d.add("LED_1", "rgb_led", (27, -6), 0)
    d.add("P_1", "potentiometer", (8, 14), 0, "10k", "0.5")
    d.connect(
        {
            "buzz": [A("D8"), ("BZ_1", 0)],
            "red": [A("D9"), ("R_1", 0)],
            "green": [A("D10"), ("R_2", 0)],
            "blue": [A("D11"), ("R_3", 0)],
            "r": [("R_1", 1), ("LED_1", 0)],
            "g": [("R_2", 1), ("LED_1", 1)],
            "b": [("R_3", 1), ("LED_1", 2)],
            "a0": [A("A0"), ("P_1", 2)],
            "5V": [A("5V"), ("P_1", 1)],
            "GND": [A("GND"), ("BZ_1", 1), ("LED_1", 3), ("P_1", 0)],
        }
    )
    L.drawing("melodia", d)
    L.code("""
# nuty z A4 = 440 Hz i dwunastego pierwiastka z dwóch
nazwy = ["A", "A#", "H", "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#"]
for polton in range(13):
    print(f"{nazwy[polton % 12]:<3} {440 * 2 ** (polton / 12):7.1f} Hz")
""")
    L.save()


def scope():
    L = Lesson(C, "17-oscyloskop", "Oscyloskop na Arduino")
    L.md("""
# Oscyloskop z Arduino

Arduino mierzy napięcie na A0 128 razy z rzędu, najszybciej jak umie (ok. 9000 pomiarów na sekundę),
i rysuje przebieg na OLED-zie. Z tego, co ile próbek przebieg przechodzi w górę przez połowę zakresu,
liczy częstotliwość. Potencjometr zmienia podstawę czasu — przerwę między próbkami.

Na wejściu jest sinusoida 50 Hz o amplitudzie 2 V, podniesiona o 2,5 V źródłem stałym: przetwornik
Arduino mierzy tylko od 0 do 5 V i ujemnych napięć by nie zobaczył. Zmień częstotliwość źródła $E_2$
i porównaj z tym, co pokazuje ekran.

**Twierdzenie o próbkowaniu:** żeby odtworzyć sygnał, trzeba mierzyć więcej niż dwa razy na jego
okres. Ustaw źródło na 2000 Hz i zobacz, co się dzieje, gdy próbek jest za mało (*aliasing*).
""")
    d = Drawing()
    d.add("ARD_1", "arduino", (0, 0), 0, None, sketch("scope.ino"))
    o = oled(d, (22, -14))
    d.add("E_1", "voltage_source", (6, 22), 270, "2.5")
    d.add("E_2", "sine_source", (6, 18), 270, "2", "50")
    d.add("R_1", "resistor", (4, 12), 0, "1k")
    d.add("P_1", "potentiometer", (14, 14), 0, "10k", "0.2")
    d.connect(
        {
            "sig": [("E_2", 1), ("R_1", 0)],
            "a0": [A("A0"), ("R_1", 1)],
            "a1": [A("A1"), ("P_1", 2)],
            "sda": [A("A4"), o["SDA"]],
            "scl": [A("A5"), o["SCL"]],
            "5V": [A("5V"), o["VCC"], ("P_1", 1)],
            "GND": [A("GND"), o["GND"], ("E_1", 0), ("P_1", 0)],
        }
    )
    L.drawing("oscyloskop", d)
    L.save()


def traffic():
    L = Lesson(C, "18-sygnalizacja", "Sygnalizacja świetlna")
    L.md("""
# Przejście dla pieszych

Samochody mają zielone, dopóki pieszy nie naciśnie przycisku. Potem: żółte, czerwone, zielone dla
pieszych z tykaniem dla niewidomych, mruganie „kończ przechodzić” — i z powrotem, przez czerwone
z żółtym. To prosta **maszyna stanów**: każdy stan to kombinacja świateł i czas, po którym przychodzi
następny.

**Jak grać:** uruchom ⚡, kliknij schemat i naciśnij **spację** (przycisk dla pieszych).
""")
    d = Drawing()
    d.add("ARD_1", "arduino", (0, 0), 0, None, sketch("traffic.ino"))
    nets = {"GND": [A("GND")]}
    for k, (pin, color) in enumerate(
        [("D8", "red"), ("D9", "yellow"), ("D10", "green"), ("D11", "red"), ("D12", "green")]
    ):
        r, cathode = led(d, k + 1, -2 - 3 * k - (2 if k >= 3 else 0), -2, color)
        nets[f"l{k}"] = [A(pin), r]
        nets["GND"].append(cathode)
    d.add("B_1", "button", (20, -10), 90, None, "Space")
    d.add("BZ_1", "buzzer", (24, -10), 90)
    nets |= {"key": [A("D2"), ("B_1", 1)], "tick": [A("D7"), ("BZ_1", 1)]}
    nets["GND"] += [("B_1", 0), ("BZ_1", 0)]
    d.connect(nets)
    L.drawing("sygnalizacja", d)
    L.save()


def hbridge():
    L = Lesson(C, "19-mostek-h", "Mostek H: silnik w obie strony")
    L.md("""
# Mostek H

Żeby silnik prądu stałego kręcił się w drugą stronę, trzeba odwrócić napięcie na jego zaciskach.
Robią to cztery tranzystory ułożone w literę **H**: silnik w poprzeczce, po dwa tranzystory z każdej
strony — górny do plusa, dolny do masy. Włączone po przekątnej (lewy górny i prawy dolny) puszczają prąd
w jedną stronę, druga przekątna — w drugą.

Tu górne tranzystory to MOSFET-y z kanałem P (włącza je stan **niski** na bramce), a dolne — z kanałem N
(włącza je stan **wysoki**). Prędkość ustawia **PWM** na dolnym tranzystorze: szybkie włączanie
i wyłączanie, średnio tyle napięcia, ile wynosi wypełnienie.

Uruchom ⚡ i przesuwaj suwak potencjometru: środek to stop, lewo i prawo — obroty w obie strony.
Nigdy nie wolno włączyć obu tranzystorów z jednej strony naraz: zwarłyby zasilanie do masy (to się
nazywa *shoot-through*). Szkic dlatego najpierw wszystko wyłącza, czeka chwilę, a dopiero potem
włącza nową parę.
""")
    d = Drawing()
    d.add("ARD_1", "arduino", (0, 0), 0, None, sketch("hbridge.ino"))
    d.add("E_1", "voltage_source", (26, 8), 270, "6")
    d.add("Q_1", "pmos", (14, -14), 0)
    d.add("Q_2", "nmos", (14, -6), 0)
    d.add("Q_3", "pmos", (30, -14), 180)
    d.add("Q_4", "nmos", (30, -6), 180)
    d.add("M_1", "motor", (19, -10), 0)
    d.add("P_1", "potentiometer", (8, 14), 0, "10k", "0.8")
    d.connect(
        {
            "gl": [A("D5"), ("Q_1", 0)],
            "ll": [A("D6"), ("Q_2", 0)],
            "gr": [A("D9"), ("Q_3", 0)],
            "lr": [A("D10"), ("Q_4", 0)],
            "6V": [("E_1", 1), ("Q_1", 2), ("Q_3", 2)],
            "a": [("Q_1", 1), ("Q_2", 1), ("M_1", 0)],
            "b": [("Q_3", 1), ("Q_4", 1), ("M_1", 1)],
            "a0": [A("A0"), ("P_1", 2)],
            "5V": [A("5V"), ("P_1", 1)],
            "GND": [A("GND"), ("E_1", 0), ("Q_2", 2), ("Q_4", 2), ("P_1", 0)],
        }
    )
    L.drawing("mostek_h", d)
    L.save()


# ------------------------------------------------------------------ analogue classics


def astable():
    L = Lesson(C, "20-multiwibrator", "Multiwibrator na dwóch tranzystorach")
    L.md("""
# Multiwibrator astabilny

Klasyk z każdego podręcznika i pierwszego zestawu do lutowania: dwa tranzystory, dwa kondensatory
i cztery oporniki, a diody mrugają na zmianę — bez żadnego układu scalonego i bez programu.

Jak to działa: kiedy $Q_1$ się włącza, jego kolektor spada do zera, a kondensator $C_1$ ciągnie bazę
$Q_2$ poniżej zera — $Q_2$ się wyłącza. $C_1$ ładuje się przez $R_2$, aż baza $Q_2$ dojdzie do ok. 0,6 V;
wtedy $Q_2$ się włącza i to samo dzieje się z drugiej strony. Każdy stan trwa ok. $0{,}69\\,R C$:

$$T \\approx 0{,}69 \\cdot (R_2 C_1 + R_3 C_2) = 0{,}69 \\cdot 2 \\cdot 47\\,\\mathrm{kΩ} \\cdot 22\\,\\mathrm{µF} \\approx 1{,}4\\,\\mathrm{s}$$

Uruchom ⚡ i zajrzyj na oscyloskop: napięcia na bazach (`V_b1`, `V_b2`) spadają pod zero przy każdym
przełączeniu i powoli wracają — to ładujące się kondensatory.
""")
    d = Drawing()
    d.add("E_1", "voltage_source", (0, 16), 270, "9")
    d.add("R_1", "resistor", (6, 0), 90, "470")
    d.add("LED_1", "led", (6, 4), 90, None, "red")
    d.add("R_2", "resistor", (12, 0), 90, "47k")
    d.add("R_3", "resistor", (16, 0), 90, "47k")
    d.add("R_4", "resistor", (22, 0), 90, "470")
    d.add("LED_2", "led", (22, 4), 90, None, "green")
    d.add("C_1", "capacitor", (6, 8), 0, "22u")
    d.add("C_2", "capacitor", (22, 9), 180, "22u")
    d.add("Q_1", "npn", (3, 12), 0)
    d.add("Q_2", "npn", (25, 12), 180)
    d.connect(
        {
            "9V": [("E_1", 1), ("R_1", 0), ("R_2", 0), ("R_3", 0), ("R_4", 0)],
            "k1": [("LED_1", 1), ("Q_1", 1), ("C_1", 0)],
            "k2": [("LED_2", 1), ("Q_2", 1), ("C_2", 0)],
            "b2": [("C_1", 1), ("R_3", 1), ("Q_2", 0)],
            "b1": [("C_2", 1), ("R_2", 1), ("Q_1", 0)],
            "GND": [("E_1", 0), ("Q_1", 2), ("Q_2", 2)],
        }
    )
    d.ground(d.pin("E_1", 0))
    d.label("b1", d.pin("Q_1", 0))
    d.label("b2", d.pin("Q_2", 0))
    L.drawing("multiwibrator", d)
    L.code("""
plot(multiwibrator.simulate(until=4), "V_b1", "V_b2")
""")
    L.save()


def amplifier():
    L = Lesson(C, "21-wzmacniacz", "Wzmacniacz tranzystorowy")
    L.md("""
# Wzmacniacz w układzie wspólnego emitera

Sygnał z mikrofonu ma kilka miliwoltów — tranzystor może go wzmocnić sto razy. Dzielnik $R_1$, $R_2$
ustawia bazę na ok. 1,6 V (**punkt pracy**): tranzystor jest trochę otwarty i może reagować na sygnał
w obie strony. Kondensator $C_1$ przepuszcza do bazy tylko zmiany (sam sygnał), nie psując punktu
pracy, a $C_3$ oddaje na wyjście tylko wzmocnione zmiany, bez stałego napięcia kolektora.

$C_2$ zwiera opornik emitera dla sygnału: bez niego wzmocnienie byłoby tylko
$\\frac{R_C}{R_E} \\approx 4{,}7$, z nim — kilkadziesiąt razy więcej. Wyjście jest **odwrócone**: gdy
na wejściu rośnie, na wyjściu spada.

Uruchom ⚡ i dodaj na oscyloskopie `V_we` i `V_wy` — albo spójrz na wykres poniżej.
""")
    d = Drawing()
    d.add("E_1", "voltage_source", (0, 18), 270, "9")
    d.add("E_2", "sine_source", (-6, 18), 270, "20m", "1k")
    d.add("C_1", "capacitor", (-4, 10), 0, "10u")
    d.add("R_1", "resistor", (4, 2), 90, "47k")
    d.add("R_2", "resistor", (4, 12), 90, "10k")
    d.add("Q_1", "npn", (8, 10), 0)
    d.add("R_C", "resistor", (11, 2), 90, "2.2k")
    d.add("R_E", "resistor", (11, 12), 90, "470")
    d.add("C_2", "capacitor", (15, 12), 90, "100u")
    d.add("C_3", "capacitor", (15, 6), 0, "10u")
    d.add("R_L", "resistor", (22, 10), 90, "10k")
    d.connect(
        {
            "9V": [("E_1", 1), ("R_1", 0), ("R_C", 0)],
            "we": [("E_2", 1), ("C_1", 0)],
            "b": [("C_1", 1), ("R_1", 1), ("R_2", 0), ("Q_1", 0)],
            "c": [("R_C", 1), ("Q_1", 1), ("C_3", 0)],
            "e": [("Q_1", 2), ("R_E", 0), ("C_2", 0)],
            "wy": [("C_3", 1), ("R_L", 0)],
            "GND": [("E_1", 0), ("E_2", 0), ("R_2", 1), ("R_E", 1), ("C_2", 1), ("R_L", 1)],
        }
    )
    d.ground(d.pin("E_1", 0))
    d.label("we", d.pin("E_2", 1))
    d.label("wy", d.pin("R_L", 0))
    L.drawing("wzmacniacz", d)
    L.code("""
p = wzmacniacz.simulate(until=0.2, dt=2e-5)
koniec = next(k for k, t in enumerate(p.t) if t >= 0.195)
we, wy = p("V_we")[koniec:], p("V_wy")[koniec:]
print(f"wzmocnienie ≈ {(max(wy) - min(wy)) / (max(we) - min(we)):.0f} razy")
plot(p, "V_we", "V_wy")
""")
    L.save()


if __name__ == "__main__":
    import sys

    intro()
    only = sys.argv[1:]
    for example in (
        doom,
        shooter,
        tetris,
        mandelbrot,
        snake,
        pong,
        flappy,
        life,
        simon,
        reflex,
        theremin,
        parking,
        thermometer,
        radar,
        dice,
        melody,
        scope,
        traffic,
        hbridge,
        astable,
        amplifier,
    ):
        if not only or example.__name__ in only:
            example()
