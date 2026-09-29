"""Builds apps/notebook/examples/nowe-elementy.electro.json: a tour of the elements added lately —
sources in time, the Zener diode, MOSFETs, controlled sources, sensors, and what an Arduino drives:
a servo, buzzers, an RGB LED, a seven-segment display, a character LCD, an HC-SR04, and I²C modules
(run from the repo root with PYTHONPATH set, e.g. in devenv shell). Each drawing is checked: a
circuit, runnable in time, and wired where it says."""
import json
import secrets
from datetime import datetime, timezone
from pathlib import Path

from electro.sim import compile_sim
from electro_schematic import Element, Schematic, Wire

cells = []
md = lambda text: cells.append({"id": secrets.token_hex(4), "type": "markdown", "source": text.strip()})
code = lambda text: cells.append({"id": secrets.token_hex(4), "type": "code", "source": text.strip(), "outputs": []})


class Drawing:
    """Elements and wires; ``label(text, at)`` puts a net label (same text: the same node, "GND": ground)."""

    def __init__(self):
        self.elements: list[Element] = []
        self.wires: list[list] = []
        self.labels = 0

    def add(self, *args) -> Element:
        e = Element(*args)
        self.elements.append(e)
        return e

    def wire(self, *points):
        self.wires.append(list(points))

    def label(self, text, at):
        self.labels += 1
        self.add(f"lbl{self.labels}", "label", at, 0, None, text)

    def ground(self, at):
        self.labels += 1
        self.add(f"gnd{self.labels}", "ground", at, 0)

    def stub(self, pin, towards, length, text):
        """A short wire from ``pin`` ``towards`` (dx, dy), and at its end the label ``text`` (None: ground)."""
        end = (pin[0] + towards[0] * length, pin[1] + towards[1] * length)
        self.wire(pin, end)
        if text is None:
            self.ground(end)
        else:
            self.label(text, end)

    def row(self, pins, towards, texts):
        """Labels on a row of pins side by side, on wires getting shorter to the right: each label's text
        (drawn to the right of its wire's end) is clear of the next wire."""
        for i, (pin, text) in enumerate(zip(pins, texts)):
            self.stub(pin, towards, len(pins) + 1 - i, text)

    def column(self, pins, texts):
        """Labels on a column of pins on a module's left, on wires out to the left getting longer downwards:
        each label's text (to the right of its wire's end, above it) has no wire over it."""
        for i, (pin, text) in enumerate(zip(pins, texts)):
            self.stub(pin, (-1, 0), 2 + 2 * i, text)

    def cell(self, name, joined=(), live=True):
        # where the drawing starts: every point a few squares from the top left (the canvas starts at 0, 0;
        # a symbol may reach 5 squares above its pins, as an HC-SR04's)
        points = [p for e in self.elements for p in e.pins()] + [p for w in self.wires for p in w]
        dx, dy = 4 - min(x for x, _ in points), 7 - min(y for _, y in points)
        self.elements = [Element(e.id, e.kind, (e.at[0] + dx, e.at[1] + dy), e.rotation, e.value, e.text) for e in self.elements]
        self.wires = [[(x + dx, y + dy) for x, y in w] for w in self.wires]
        sch = Schematic(self.elements, [Wire(w) for w in self.wires])
        sch.to_circuit()  # it must be a circuit
        if live:
            compile_sim(sch.to_circuit())  # …that runs in time
        names = sch.node_names()
        pins = {e.id: e.pins() for e in self.elements}
        for group in joined:  # (element id, pin index), all on one node
            nodes = {names.get(pins[i][k]) for i, k in group}
            assert len(nodes) == 1 and None not in nodes, (name, group, nodes)
        cells.append({"id": secrets.token_hex(4), "type": "schematic", "name": name, "schematic": json.loads(sch.to_json())})


# an Uno's pins (electro_schematic: KINDS["arduino"]), by name → index
PIN = {f"D{i}": i for i in range(14)} | {f"A{i}": 14 + i for i in range(6)} | {"5V": 20, "GND": 21}


def uno(d: Drawing, sketch: str, labels: dict[str, str]) -> Element:
    """An Arduino at (0, 0) with its sketch, and net labels on the pins named: {"D9": "SERVO", …}."""
    board = d.add("ARD_1", "arduino", (0, 0), 0, None, sketch)
    for pin, text in labels.items():
        d.label(text, board.pins()[PIN[pin]])
    return board


md("""
Przegląd elementów dodanych ostatnio. Schematy uruchamiasz przyciskiem **▶ Symuluj w czasie** pod każdym
z nich: przewody zmieniają kolor z napięciem, a oscyloskop pod schematem pokazuje przebiegi. Czujniki
(fotorezystor, termistor, czujnik odległości) mają w czasie symulacji suwak — kliknij element.
Szkice Arduino kompilują się w przeglądarce; biblioteki `Servo`, `LiquidCrystal`, `LiquidCrystal_I2C`,
`Adafruit_SSD1306` i `RTClib` są dostępne od razu.
""")

# ------------------------------------------------------------------ 1. sources in time

md("""
## 1. Źródła zmienne w czasie
**Źródło sinusoidalne** (amplituda i częstotliwość) na filtrze RC: przy częstotliwości granicznej
$f_g = \\frac{1}{2\\pi RC} \\approx 48$ Hz na kondensatorze zostaje $\\frac{1}{\\sqrt 2}$ amplitudy, opóźnione.
Porównaj na oscyloskopie `V_we` i `V_wy`.
""")
d = Drawing()
d.add("E_1", "sine_source", (0, 8), 270, "5", "50")
d.add("R_1", "resistor", (4, 0), 0, "1k")
d.add("C_1", "capacitor", (12, 0), 90, "3.3u")
d.wire((0, 4), (0, 0), (4, 0))
d.wire((8, 0), (12, 0))
d.wire((12, 4), (12, 8), (0, 8))
d.ground((0, 8))
d.label("we", (0, 4))  # at the source: labels join where pins and wire ends are, not at a bend
d.label("wy", (12, 0))
d.cell("filtr", joined=[[("E_1", 1), ("R_1", 0)]])

md("""
**Generator prostokąta** (poziom, częstotliwość, wypełnienie): 2 Hz z wypełnieniem 25 % — dioda błyska
krótko dwa razy na sekundę. Zmień wypełnienie suwakiem w panelu źródła.
""")
d = Drawing()
d.add("E_1", "square_source", (0, 8), 270, "5", "2 25%")
d.add("R_1", "resistor", (4, 0), 0, "220")
d.add("LED_1", "led", (12, 0), 90, None, "green")
d.wire((0, 4), (0, 0), (4, 0))
d.wire((8, 0), (12, 0))
d.wire((12, 4), (12, 8), (0, 8))
d.ground((0, 8))
d.cell("migacz_prostokat")

md("W kodzie: `SineSource(amplituda, frequency=…)`, `SquareSource(poziom, frequency=…, duty=…)`.")
code("""
przebieg = simulate(filtr, t=0.1)
przebieg.plot("V_we", "V_wy")
""")

# ------------------------------------------------------------------ 2. Zener

md("""
## 2. Dioda Zenera — stabilizator napięcia
Zener 5,1 V w kierunku zaporowym trzyma napięcie na obciążeniu, choć zasilanie jest wyższe; nadmiar
odkłada się na $R_1$. W symulacji woltomierz pokazuje ok. 5,1 V — zmień napięcie $E_1$ albo obciążenie $R_2$.
""")
d = Drawing()
d.add("E_1", "voltage_source", (0, 8), 270, "12")
d.add("R_1", "resistor", (4, 0), 0, "470")
d.add("DZ_1", "zener", (8, 8), 270, "5.1")
d.add("R_2", "resistor", (12, 0), 90, "1k")
d.add("V_1", "voltmeter", (16, 0), 90)
d.wire((0, 4), (0, 0), (4, 0))
d.wire((8, 0), (8, 4))
d.wire((8, 0), (12, 0))
d.wire((12, 0), (16, 0))
d.wire((0, 8), (8, 8))
d.wire((8, 8), (12, 8))
d.wire((12, 4), (12, 8))
d.wire((12, 8), (16, 8))
d.wire((16, 4), (16, 8))
d.ground((0, 8))
d.cell("stabilizator", joined=[[("DZ_1", 1), ("R_2", 0), ("V_1", 0)]])

md("Ogranicznik: sinus 10 V obcięty z góry do 5,1 V (przebicie), z dołu do ok. −0,7 V (przewodzenie).")
code("""
ogranicznik = net(
    (SineSource(10, frequency=50), "GND", "we"),
    (Resistor(1000), "we", "wy"),
    (Zener(5.1), "GND", "wy"),
)
simulate(ogranicznik, t=0.04).plot("V_we", "V_wy")
""")

# ------------------------------------------------------------------ 3. MOSFET

md("""
## 3. MOSFET jako klucz
Prostokąt 1 Hz na bramce tranzystora N-MOSFET: powyżej napięcia progowego (2 V) kanał przewodzi
(ok. 0,7 Ω) i dioda świeci. Bramka pobiera prąd tylko przy przeładowaniu swojej pojemności — zobacz `I_Q_1_G`
na mierniku. W kodzie: `NMOS()`, `PMOS()` — bramka, dren, źródło.
""")
d = Drawing()
d.add("E_1", "voltage_source", (-4, 10), 270, "12")
d.add("R_1", "resistor", (8, 0), 90, "470")
d.add("LED_1", "led", (8, 4), 90, None, "blue")
d.add("Q_1", "nmos", (5, 10), 0)
d.add("R_2", "resistor", (1, 10), 0, "100")
d.add("E_2", "square_source", (1, 14), 270, "5", "1")
d.wire((-4, 6), (-4, 0), (8, 0))
d.wire((-4, 10), (-4, 16), (1, 16))
d.wire((1, 16), (8, 16))
d.wire((1, 14), (1, 16))
d.wire((8, 12), (8, 16))
d.ground((-4, 16))
d.cell("klucz", joined=[[("LED_1", 1), ("Q_1", 1)], [("R_2", 1), ("Q_1", 0)]])

# ------------------------------------------------------------------ 4. controlled sources

md("""
## 4. Źródła sterowane — na papierze, krok po kroku
Wzmacniacz napięciowy jako **źródło napięcia sterowane napięciem** ($\\mu = 10$): lewa para zacisków
mierzy napięcie, prawa jest źródłem. Uruchom komórkę przyciskiem ▶ — to obwód liniowy, więc solver
rozwiązuje go na papierze.
""")
d = Drawing()
d.add("E_1", "voltage_source", (0, 4), 270, "1")
d.add("VCVS_1", "vcvs", (4, 0), 0, "10")
d.add("R_1", "resistor", (12, 0), 90, "50")
d.wire((0, 0), (4, 0))
d.wire((0, 4), (4, 4))
d.wire((4, 4), (8, 4))
d.wire((8, 0), (12, 0))
d.wire((8, 4), (12, 4))
d.ground((0, 4))
d.cell("wzmacniacz", live=False)

md("""
Źródło prądu sterowane prądem jako model tranzystora: prąd bazy płynie przez gałąź pomiarową (ze strzałką),
kolektor to źródło $\\beta \\cdot I_b$. Z pomiaru napięcia na $R_2$ solver wyznacza $\\beta$.
""")
code("""
stopien = net(
    (VoltageSource("10m"), "GND", "we"),
    (Resistor(1000), "we", "b"),       # r_be
    (CCCS(), "b", "GND", "GND", "c"),  # β · I_b
    (Resistor(2000), "c", "GND"),
)
sol = stopien.solve(U_R_2=2, find="CCCS_1")
steps(sol)
""")

# ------------------------------------------------------------------ 5. sensors

md("""
## 5. Czujniki: światło i temperatura
Dzielniki z **fotorezystorem** (10 kΩ przy 10 lx) i **termistorem NTC** (10 kΩ przy 25 °C). Na papierze
liczą się przy świetle i temperaturze ustawionych w panelu; w symulacji zmieniasz je suwakiem, a woltomierze
nadążają. Ciemniej — większy opór fotorezystora; cieplej — mniejszy termistora.
""")
d = Drawing()
d.add("E_1", "voltage_source", (0, 8), 270, "5")
d.add("R_1", "resistor", (4, 0), 90, "10k")
d.add("LDR_1", "photoresistor", (4, 4), 90, "10k", "100")
d.add("V_1", "voltmeter", (8, 4), 90)
d.add("R_2", "resistor", (14, 0), 90, "10k")
d.add("RT_1", "thermistor", (14, 4), 90, "10k", "25")
d.add("V_2", "voltmeter", (18, 4), 90)
d.wire((0, 4), (0, 0), (4, 0))
d.wire((4, 0), (14, 0))
d.wire((4, 4), (8, 4))
d.wire((14, 4), (18, 4))
d.wire((0, 8), (4, 8))
d.wire((4, 8), (8, 8))
d.wire((8, 8), (14, 8))
d.wire((14, 8), (18, 8))
d.ground((0, 8))
d.cell("czujniki", joined=[[("LDR_1", 0), ("V_1", 0)], [("RT_1", 0), ("V_2", 0)]])

# ------------------------------------------------------------------ 6. Arduino: servo, buzzer

md("""
## 6. Arduino: serwo i buzzer
Potencjometr na A0 ustawia kąt serwa (biblioteka `Servo`: impulsy 0,54–2,4 ms na D9), a buzzer pasywny
na D6 gra `tone()` tym wyższy, im dalej suwak. Buzzer słychać — na pasku symulacji jest przycisk wyciszenia.
Połączenia oznaczone etykietami (5V, GND, SERWO, BUZZER) są połączone, choć nie ma między nimi przewodu.
""")
SERVO = """#include <Servo.h>

Servo serwo;

void setup() {
  serwo.attach(9);
}

void loop() {
  int v = analogRead(A0);        // 0–1023 z potencjometru
  serwo.write(map(v, 0, 1023, 0, 180));
  tone(6, 200 + v, 60);          // krótki ton, wyższy im dalej suwak
  delay(250);
}
"""
d = Drawing()
board = uno(d, SERVO, {"D9": "SERWO", "D6": "BUZZER", "5V": "5V", "GND": "GND"})
servo = d.add("M_1", "servo", (26, -6), 0)
d.column(servo.pins(), ["SERWO", "5V", "GND"])
d.add("BZ_1", "passive_buzzer", (24, 4), 0)
d.stub((24, 4), (-1, 0), 4, "BUZZER")
d.ground((28, 4))
d.add("P_1", "potentiometer", (8, 12), 0, "10k", "0.5")
d.wire(board.pins()[PIN["A0"]], (9, 9), (10, 9), (10, 10))
d.label("5V", (8, 12))
d.label("GND", (12, 12))
d.cell("serwo", joined=[[("ARD_1", PIN["D9"]), ("M_1", 0)], [("ARD_1", PIN["A0"]), ("P_1", 2)],
                        [("ARD_1", PIN["D6"]), ("BZ_1", 0)]])

# ------------------------------------------------------------------ 7. seven segments, RGB

md("""
## 7. Wyświetlacz 7-segmentowy i dioda RGB
Licznik 0–9 na wyświetlaczu ze wspólną katodą (segmenty a–g na D2–D8, jeden rezystor na katodzie —
dlatego cyfry z większą liczbą segmentów świecą ciemniej), a dioda RGB płynnie zmienia kolor (PWM na D9–D11).
""")
SEGMENTS = """// segmenty a–g na pinach 2–8; bit 0 = a … bit 6 = g
const byte SEG[] = {2, 3, 4, 5, 6, 7, 8};
const byte CYFRY[10] = {0b0111111, 0b0000110, 0b1011011, 0b1001111, 0b1100110,
                        0b1101101, 0b1111101, 0b0000111, 0b1111111, 0b1101111};

void setup() {
  for (byte s : SEG) pinMode(s, OUTPUT);
}

void loop() {
  for (int n = 0; n < 10; n++) {
    for (int i = 0; i < 7; i++) digitalWrite(SEG[i], (CYFRY[n] >> i) & 1);
    for (int k = 0; k < 50; k++) {        // przez sekundę kolor diody RGB krąży po tęczy
      float h = (n * 50 + k) / 500.0 * 6.283;
      analogWrite(9, 127 + 127 * sin(h));
      analogWrite(10, 127 + 127 * sin(h + 2.094));
      analogWrite(11, 127 + 127 * sin(h + 4.189));
      delay(20);
    }
  }
}
"""
d = Drawing()
segs = "abcdefg"
uno(d, SEGMENTS, {f"D{2 + i}": s for i, s in enumerate(segs)} | {"D9": "R", "D10": "G", "D11": "B", "GND": "GND"})
ds = d.add("DS_1", "seven_segment", (22, -4), 0)
for i, s in enumerate(segs):
    d.label(s, ds.pins()[i])
d.add("R_1", "resistor", ds.pins()[8], 270, "220")  # from the common cathode, one resistor to ground
d.wire((24, -8), (28, -8))
d.ground((28, -8))
for k, (c, y) in enumerate(zip("RGB", (6, 8, 10))):
    d.add(f"R_{k + 2}", "resistor", (22, y), 0, "220")
    d.label(c, (22, y))
d.add("LED_1", "rgb_led", (26, 6), 0)
d.ground((30, 8))
d.cell("licznik", joined=[[("ARD_1", PIN["D2"]), ("DS_1", 0)], [("ARD_1", PIN["D8"]), ("DS_1", 6)],
                          [("ARD_1", PIN["D10"]), ("R_3", 0)], [("R_3", 1), ("LED_1", 1)]])

# ------------------------------------------------------------------ 8. LCD + HC-SR04

md("""
## 8. Czujnik odległości HC-SR04 i wyświetlacz LCD 16×2
Szkic co chwilę wysyła impuls na TRIG (10 µs), mierzy `pulseIn()` długość echa (58 µs na centymetr) i pisze
odległość na LCD (biblioteka `LiquidCrystal`, tryb 4-bitowy: RS, E, D4–D7). Przesuń przeszkodę suwakiem
czujnika. V0 przy masie daje najciemniejsze znaki; podświetlenie to dioda między A i K.
""")
DISTANCE = """#include <LiquidCrystal.h>

LiquidCrystal lcd(12, 11, 5, 4, 3, 2);   // RS, E, D4, D5, D6, D7
const int TRIG = 9, ECHO = 7;

void setup() {
  lcd.begin(16, 2);
  lcd.print("Odleglosc:");
  pinMode(TRIG, OUTPUT);
  pinMode(ECHO, INPUT);
}

void loop() {
  digitalWrite(TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG, LOW);
  long us = pulseIn(ECHO, HIGH, 30000UL);
  lcd.setCursor(0, 1);
  if (us == 0) lcd.print("poza zasiegiem  ");
  else {
    lcd.print(us / 58);
    lcd.print(" cm            ");
  }
  delay(200);
}
"""
d = Drawing()
uno(d, DISTANCE, {"D12": "RS", "D11": "E", "D5": "D4", "D4": "D5", "D3": "D6", "D2": "D7", "D9": "TRIG", "D7": "ECHO",
                  "5V": "5V", "GND": "GND"})
lcd = d.add("LCD_1", "lcd1602", (22, -2), 0)
pins = lcd.pins()
for i in (0, 2, 4):  # VSS, V0 (at ground: the darkest), RW (writing only): one rail to ground
    d.wire(pins[i], (pins[i][0], -4))
d.wire((21, -4), (22, -4))
d.wire((22, -4), (24, -4))
d.wire((24, -4), (26, -4))
d.ground((21, -4))
for i, text in {1: "5V", 3: "RS", 5: "E", 10: "D4", 11: "D5", 12: "D6", 13: "D7"}.items():
    d.label(text, pins[i])
d.add("R_1", "resistor", pins[14], 270, "220")  # the backlight's resistor, from A up to 5 V
d.label("5V", (36, -6))
d.wire(pins[15], (37, -4), (38, -4))
d.ground((38, -4))
us = d.add("US_1", "ultrasonic", (4, -14), 0, None, "80")
d.row(us.pins(), (0, 1), ["5V", "TRIG", "ECHO", None])
d.cell("odleglosc", joined=[[("ARD_1", PIN["D12"]), ("LCD_1", 3)], [("ARD_1", PIN["D7"]), ("US_1", 2)],
                            [("ARD_1", PIN["5V"]), ("LCD_1", 1), ("US_1", 0)]])

# ------------------------------------------------------------------ 9. I²C

md("""
## 9. I²C: zegar, OLED i LCD z konwerterem
Trzy moduły na jednej magistrali: SDA do A4, SCL do A5 (etykiety). Zegar **DS1307** startuje od czasu na
Twoim komputerze; **OLED** 128×64 (`Adafruit_SSD1306`, adres 0x3C) pokazuje godzinę dużymi cyframi,
a **LCD z konwerterem PCF8574** (`LiquidCrystal_I2C`, 0x27) datę. Adres modułu zmienisz w jego panelu —
wtedy szkic go nie znajdzie, jak w prawdziwym układzie.
""")
CLOCK = """#include <Wire.h>
#include <RTClib.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <LiquidCrystal_I2C.h>

RTC_DS1307 zegar;
Adafruit_SSD1306 oled(128, 64, &Wire, -1);
LiquidCrystal_I2C lcd(0x27, 16, 2);

void dwie(Print &p, int n) {   // zawsze dwie cyfry: 09, 10, …
  if (n < 10) p.print('0');
  p.print(n);
}

void setup() {
  zegar.begin();
  oled.begin(SSD1306_SWITCHCAPVCC, 0x3C);
  oled.setTextColor(SSD1306_WHITE);
  lcd.init();
  lcd.backlight();
}

void loop() {
  DateTime t = zegar.now();
  oled.clearDisplay();
  oled.setTextSize(3);
  oled.setCursor(20, 20);
  dwie(oled, t.hour());
  oled.print(':');
  dwie(oled, t.minute());
  oled.setTextSize(1);
  oled.setCursor(56, 52);
  dwie(oled, t.second());
  oled.display();
  lcd.setCursor(0, 0);
  lcd.print("Data:");
  lcd.setCursor(0, 1);
  dwie(lcd, t.day());
  lcd.print('.');
  dwie(lcd, t.month());
  lcd.print('.');
  lcd.print(t.year());
  delay(200);
}
"""
d = Drawing()
board = uno(d, CLOCK, {"5V": "5V", "GND": "GND"})
d.row([board.pins()[PIN["A4"]], board.pins()[PIN["A5"]]], (0, 1), ["SDA", "SCL"])
rtc = d.add("RTC_1", "ds1307", (28, 12), 0, None, "0x68")
oled = d.add("OLED_1", "ssd1306", (28, -14), 0, None, "0x3C")
lcd = d.add("LCD_1", "lcd1602_i2c", (28, 22), 0, None, "0x27")
for module in (rtc, lcd):
    d.column(module.pins(), ["GND", "5V", "SDA", "SCL"])
d.row(oled.pins(), (0, -1), ["GND", "5V", "SCL", "SDA"])
d.cell("zegar", joined=[[("ARD_1", PIN["A4"]), ("RTC_1", 2), ("OLED_1", 3), ("LCD_1", 2)],
                        [("ARD_1", PIN["A5"]), ("RTC_1", 3), ("OLED_1", 2), ("LCD_1", 3)]])

md("""
## W kodzie
Każdy z tych elementów jest też w Pythonie — `code()` zapisze schemat jako kod:
`Photoresistor(10000, lux=100)`, `Thermistor(10000, temperature=25)`, `Zener(5.1)`, `NMOS()`, `VCVS(10)`,
`Servo()`, `Buzzer()`, `PassiveBuzzer()`, `RGBLED()`, `SevenSegment()`, `LCD1602()`, `Ultrasonic(distance=80)`,
`LCD1602I2C()`, `SSD1306()`, `DS1307()`.
""")
code("""
code(czujniki)
""")

now = datetime.now(timezone.utc).isoformat(timespec="seconds")
notebook = {
    "format": "electro-notebook", "version": 2, "id": secrets.token_hex(8), "title": "Nowe elementy",
    "created": now, "modified": now, "settings": {"codeInPdf": True}, "cells": cells,
}
path = Path(__file__).parent.parent / "examples/nowe-elementy.electro.json"
path.write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(path)
