"""Builds apps/notebook/examples/nowe-elementy.electro.json: a tour of the elements added lately —
sources in time, the Zener diode, MOSFETs, controlled sources, sensors, and what an Arduino drives:
a servo, buzzers, an RGB LED, a seven-segment display, a character LCD, an HC-SR04, and I²C modules
(run from the repo root with PYTHONPATH set, e.g. in devenv shell). Each drawing is checked: a
circuit, runnable in time, and wired where it says."""

import heapq
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
        self.nets: dict[str, list] = {}

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

    def connect(self, nets: dict[str, list]):
        """Wires for the nets (name → [(element id, pin index), …]), routed (Router); checked in cell()."""
        self.nets |= nets
        Router(self).route(nets)

    def cell(self, name, joined=(), live=True):
        # where the drawing starts: every point a few squares from the top left (the canvas starts at 0, 0;
        # a symbol may reach 5 squares above its pins, as an HC-SR04's)
        points = [p for e in self.elements for p in e.pins()] + [p for w in self.wires for p in w]
        dx, dy = 4 - min(x for x, _ in points), 7 - min(y for _, y in points)
        self.elements = [
            Element(e.id, e.kind, (e.at[0] + dx, e.at[1] + dy), e.rotation, e.value, e.text) for e in self.elements
        ]
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
        # each net on a node of its own: no wire crossing another has joined it
        found = {net: {names.get(pins[i][k]) for i, k in group} for net, group in self.nets.items()}
        for net, nodes in found.items():
            assert len(nodes) == 1 and None not in nodes, (name, net, nodes)
        assert len({next(iter(n)) for n in found.values()}) == len(found), (name, found)
        cells.append(
            {"id": secrets.token_hex(4), "type": "schematic", "name": name, "schematic": json.loads(sch.to_json())}
        )


# ------------------------------------------------------------------ wires routed between pins

# where a module's body is (rotation 0, grid squares from its first pin, both ends in): no wire goes there
BODIES = {
    "arduino": (1, 17, 1, 7),
    "servo": (1, 5, -1, 3),
    "seven_segment": (0, 4, 1, 5),
    "rgb_led": (1, 3, -1, 5),
    "lcd1602": (0, 15, 1, 6),
    "ultrasonic": (-2, 5, -2, 3),
    "lcd1602_i2c": (1, 18, -2, 4),
    "ssd1306": (-4, 7, 1, 8),
    "ds1307": (1, 6, -2, 4),
    "potentiometer": (1, 3, -1, 0),
    "passive_buzzer": (1, 3, -1, 0),
    "pico": (1, 7, -2, 16),
    "ili9341": (1, 21, -3, 12),
}
BEND = 4  # a bend costs as much as this many squares of wire


class Router:
    """Wires for nets on a drawing, along the grid: around the bodies and the other nets' pins, a net's
    wire never along another's and across one only at right angles (never at its bend or end); a net
    of several pins a tree — a branch ends on the wire it joins, which is split there (wires join
    only at their ends)."""

    def __init__(self, d: "Drawing"):
        self.d = d
        self.blocked: set = set()
        for e in d.elements:
            if e.kind in BODIES:
                assert e.rotation == 0, e.id
                x0, x1, y0, y1 = BODIES[e.kind]
                ax, ay = e.at
                self.blocked |= {(ax + x, ay + y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)}
            pins = e.pins()
            if len(pins) == 2:  # a two-pin element: its body lies between its pins
                (x0, y0), (x1, y1) = pins
                self.blocked |= {(x0 + (x1 - x0) * k // 4, y0 + (y1 - y0) * k // 4) for k in (1, 2, 3)}
            if e.kind == "ground":
                self.blocked |= {(e.at[0] + dx, e.at[1] + 1) for dx in (-1, 0, 1)}
        self.pins = {p for e in d.elements for p in e.pins()}
        self.edges: set = set()  # grid edges taken
        self.through: dict = {}  # a point a wire goes straight through → "h" / "v"
        self.corners: set = set()  # wires' bends and ends
        self.crossed: set = set()  # where one net's wire crosses another's
        xs = [p[0] for p in self.blocked | self.pins]
        ys = [p[1] for p in self.blocked | self.pins]
        self.box = (min(xs) - 6, max(xs) + 6, min(ys) - 6, max(ys) + 6)

    def route(self, nets: dict[str, list]) -> dict:
        """nets: name → [(element id, pin index), …]; the wires are added to the drawing. Returns name → points."""
        at = {e.id: e.pins() for e in self.d.elements}
        points = {name: [at[i][k] for i, k in pins] for name, pins in nets.items()}
        mine = {p: name for name, ps in points.items() for p in ps}
        # the short ones first: they have the fewest ways round
        for name in sorted(
            points, key=lambda n: sum(abs(p[0] - q[0]) + abs(p[1] - q[1]) for p in points[n] for q in points[n])
        ):
            ps = points[name]
            reached = {ps[0]}
            wires: list[list] = []  # each a list of every grid point it passes
            for p in sorted(ps[1:], key=lambda p: min(abs(p[0] - q[0]) + abs(p[1] - q[1]) for q in reached)):
                if p in reached:  # on the net already (a pin on another's pin)
                    continue
                avoid = {q for q in self.pins if mine.get(q) != name or (q not in reached and q != p)}
                path = self.search(p, reached - self.crossed, avoid)
                assert path, f"no way for {name} to {p}"
                end = path[-1]
                for w in wires:  # the branch ends inside one of this net's wires: split it there
                    if end in w[1:-1]:
                        k = w.index(end)
                        wires.remove(w)
                        wires += [w[: k + 1], w[k:]]
                        self.corners.add(end)
                        self.through.pop(end, None)
                        break
                wires.append(path)
                reached |= set(path)
                self.take(self.corners_of(path))
            for w in wires:
                self.d.wire(*self.corners_of(w))
        return points

    @staticmethod
    def cells(wire):
        out = [wire[0]]
        for (x0, y0), (x1, y1) in zip(wire, wire[1:]):
            n = abs(x1 - x0) + abs(y1 - y0)
            out += [(x0 + (x1 - x0) * k // n, y0 + (y1 - y0) * k // n) for k in range(1, n + 1)]
        return out

    @staticmethod
    def corners_of(path):
        path = Router.cells(path) if len(path) > 1 else path
        keep = [path[0]]
        for a, b, c in zip(path, path[1:], path[2:]):
            if (b[0] - a[0], b[1] - a[1]) != (c[0] - b[0], c[1] - b[1]):
                keep.append(b)
        return keep + [path[-1]]

    def take(self, wire):
        cells = self.cells(wire)
        for a, b in zip(cells, cells[1:]):
            self.edges.add(frozenset((a, b)))
        corners = set(wire)
        self.corners |= corners
        for a, b in zip(cells, cells[1:-1]):
            if b not in corners:
                if b in self.through:
                    self.crossed.add(b)
                self.through[b] = "h" if a[1] == b[1] else "v"

    def search(self, start, targets, avoid):
        x0, x1, y0, y1 = self.box
        h = lambda p: min(abs(p[0] - t[0]) + abs(p[1] - t[1]) for t in targets)
        queue = [(h(start), 0, start, None, (start,))]
        best = {}
        while queue:
            _, cost, p, heading, path = heapq.heappop(queue)
            if p in targets and p != start:
                return list(path)
            if best.get((p, heading), 1e9) <= cost:
                continue
            best[(p, heading)] = cost
            crossing = p in self.through and p != start  # across another wire: straight on only
            for step in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if crossing and step != heading:
                    continue
                q = (p[0] + step[0], p[1] + step[1])
                if not (x0 <= q[0] <= x1 and y0 <= q[1] <= y1) or q in self.blocked or frozenset((p, q)) in self.edges:
                    continue
                if q in targets:
                    pass
                elif q in avoid or q in self.corners or q in path:
                    continue
                elif q in self.through and self.through[q] == ("h" if step[1] == 0 else "v"):
                    continue
                turn = heading is not None and step != heading
                heapq.heappush(queue, (cost + 1 + BEND * turn + h(q), cost + 1 + BEND * turn, q, step, path + (q,)))
        return None


# an Uno's pins (electro_schematic: KINDS["arduino"]), by name → index
PIN = {f"D{i}": i for i in range(14)} | {f"A{i}": 14 + i for i in range(6)} | {"5V": 20, "GND": 21}


def uno(d: Drawing, sketch: str) -> Element:
    """An Arduino at (0, 0) with its sketch."""
    return d.add("ARD_1", "arduino", (0, 0), 0, None, sketch)


A = lambda pin: ("ARD_1", PIN[pin])  # an Arduino's pin in a net
# a Pico's pins (electro_schematic: KINDS["pico"]): GP0–GP22, GP26–GP28, VBUS, 3V3, GND
PICO = {f"GP{i}": i for i in range(23)} | {"GP26": 23, "GP27": 24, "GP28": 25, "VBUS": 26, "3V3": 27, "GND": 28}
PI = lambda pin: ("PICO_1", PICO[pin])


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
uno(d, SERVO)
d.add("M_1", "servo", (24, -6), 0)
d.add("BZ_1", "passive_buzzer", (22, 4), 0)
d.add("P_1", "potentiometer", (8, 13), 0, "10k", "0.5")
d.connect(
    {
        "servo": [A("D9"), ("M_1", 0)],
        "buzzer": [A("D6"), ("BZ_1", 0)],
        "wiper": [A("A0"), ("P_1", 2)],
        "5V": [A("5V"), ("M_1", 1), ("P_1", 0)],
        "GND": [A("GND"), ("M_1", 2), ("BZ_1", 1), ("P_1", 1)],
    }
)
d.cell("serwo")

# ------------------------------------------------------------------ 7. seven segments, RGB

md("""
## 7. Wyświetlacz 7-segmentowy i dioda RGB
Licznik 0–9 na wyświetlaczu ze wspólną katodą (segmenty a–g na D2–D8, każdy przez swój rezystor 220 Ω:
ok. 12 mA na segment, więc każda cyfra świeci tak samo jasno — z jednym wspólnym rezystorem na katodzie prąd
dzieliłby się między zapalone segmenty i „8” byłaby ciemniejsza niż „1”), a dioda RGB płynnie zmienia kolor
(PWM na D9–D11).
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
uno(d, SEGMENTS)
d.add("DS_1", "seven_segment", (27, -22), 0)
for i in range(7):  # a resistor for each segment, a → g, standing between the board and the display
    d.add(f"R_{i + 1}", "resistor", (20 + 2 * i, -4), 270, "220")
for k, y in enumerate((4, 6, 8)):
    d.add(f"R_{k + 8}", "resistor", (22, y), 0, "220")
d.add("LED_1", "rgb_led", (27, 4), 0)
d.connect(
    {f"to_{s}": [A(f"D{2 + i}"), (f"R_{i + 1}", 0)] for i, s in enumerate("abcdefg")}
    | {f"seg_{s}": [(f"R_{i + 1}", 1), ("DS_1", i)] for i, s in enumerate("abcdefg")}
    | {
        "red": [A("D9"), ("R_8", 0)],
        "green": [A("D10"), ("R_9", 0)],
        "blue": [A("D11"), ("R_10", 0)],
        "r": [("R_8", 1), ("LED_1", 0)],
        "g": [("R_9", 1), ("LED_1", 1)],
        "b": [("R_10", 1), ("LED_1", 2)],
        "GND": [A("GND"), ("DS_1", 8), ("LED_1", 3)],
    }
)
d.cell("licznik")

# ------------------------------------------------------------------ 8. LCD + HC-SR04

md("""
## 8. Czujnik odległości HC-SR04 i wyświetlacz LCD 16×2
Szkic co chwilę wysyła impuls na TRIG (10 µs), mierzy `pulseIn()` długość echa (58 µs na centymetr) i pisze
odległość na LCD (biblioteka `LiquidCrystal`, tryb 4-bitowy: RS, E, D4–D7). Przesuń przeszkodę suwakiem
czujnika. Kontrast ustawia potencjometr na V0, jak w prawdziwym układzie — pokręć nim w czasie symulacji
(kliknij go albo zakładka **Regulacja**): za mało i znaki znikają, za dużo i wychodzą ciemne kratki.
RW jest przy masie (tylko zapis); podświetlenie to dioda między A i K, przez rezystor.
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
uno(d, DISTANCE)
d.add("LCD_1", "lcd1602", (22, -18), 0)
d.add("R_1", "resistor", (36, -18), 270, "220")  # the backlight's resistor, from A up
d.add("US_1", "ultrasonic", (-12, -8), 0, None, "80")
d.add("P_1", "potentiometer", (14, -24), 0, "10k", "0.87")  # contrast: its wiper to V0 (about 0.65 V)
L = lambda i: ("LCD_1", i)
d.connect(
    {
        "rs": [A("D12"), L(3)],
        "e": [A("D11"), L(5)],
        "d4": [A("D5"), L(10)],
        "d5": [A("D4"), L(11)],
        "d6": [A("D3"), L(12)],
        "d7": [A("D2"), L(13)],
        "trig": [A("D9"), ("US_1", 1)],
        "echo": [A("D7"), ("US_1", 2)],
        "5V": [A("5V"), L(1), ("R_1", 1), ("US_1", 0), ("P_1", 0)],
        "GND": [A("GND"), L(0), L(4), L(15), ("US_1", 3), ("P_1", 1)],
        "v0": [("P_1", 2), L(2)],
    }
)
d.cell("odleglosc")

# ------------------------------------------------------------------ 9. I²C

md("""
## 9. I²C: zegar, OLED i LCD z konwerterem
Trzy moduły na jednej magistrali: SDA do A4, SCL do A5. Zegar **DS1307** startuje od czasu na
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
uno(d, CLOCK)
d.add("RTC_1", "ds1307", (26, 10), 0, None, "0x68")
d.add("OLED_1", "ssd1306", (28, -14), 0, None, "0x3C")
d.add("LCD_1", "lcd1602_i2c", (26, 18), 0, None, "0x27")
d.connect(
    {
        "SDA": [A("A4"), ("RTC_1", 2), ("OLED_1", 3), ("LCD_1", 2)],
        "SCL": [A("A5"), ("RTC_1", 3), ("OLED_1", 2), ("LCD_1", 3)],
        "5V": [A("5V"), ("RTC_1", 1), ("OLED_1", 1), ("LCD_1", 1)],
        "GND": [A("GND"), ("RTC_1", 0), ("OLED_1", 0), ("LCD_1", 0)],
    }
)
d.cell("zegar")

# ------------------------------------------------------------------ 10. Pico: a game

md("""
## 10. Raspberry Pi Pico: strzelanka w stylu Dooma
Druga płytka: **Raspberry Pi Pico** (RP2040, logika 3,3 V). Szkic kompiluje przeglądarka (rdzeń arduino-pico;
za pierwszym razem pobiera kompilator, bez logowania). Na nim gra: korytarze liczone metodą rzucania promieni
(jak w Wolfensteinie 3D), ściany cieniowane ditheringiem, demony jako sprite'y — na OLED-zie 128×64 przez I²C
(GP4 SDA, GP5 SCL), z buzzerem na GP15.

Sterowanie: przyciski mają przypisane klawisze — **kliknij schemat** (żeby miał fokus) i graj **strzałkami**,
**spacja** strzela i zaczyna grę. Można też trzymać przyciski myszką albo w zakładce **Regulacja**.
To jeszcze nie prawdziwy Doom — ten jest niżej.
""")
GAME = (Path(__file__).parent.parent / "src/features/simulation/fixtures/hell.pico.ino").read_text()
d = Drawing()
d.add("PICO_1", "pico", (0, 0), 0, None, GAME)
d.add("OLED_1", "ssd1306", (-14, -8), 0, None, "0x3C")
d.add("BZ_1", "passive_buzzer", (-6, 9), 0)
keys = {"GP10": "ArrowUp", "GP11": "ArrowDown", "GP12": "ArrowLeft", "GP13": "ArrowRight", "GP14": "Space"}
for k, key in enumerate(keys.values()):
    d.add(f"B_{k + 1}", "button", (-4 - 3 * k, 19), 90, None, key)
d.connect(
    {
        "sda": [PI("GP4"), ("OLED_1", 3)],
        "scl": [PI("GP5"), ("OLED_1", 2)],
        "buzz": [PI("GP15"), ("BZ_1", 0)],
        **{f"key_{pin}": [PI(pin), (f"B_{k + 1}", 0)] for k, pin in enumerate(keys)},
        "3V3": [PI("3V3"), ("OLED_1", 1)],
        "GND": [PI("GND"), ("OLED_1", 0), ("BZ_1", 1), *[(f"B_{k + 1}", 1) for k in range(len(keys))]],
    }
)
d.cell("pico_gra")

# ------------------------------------------------------------------ 11. Pico: the real Doom

md("""
## 11. Prawdziwy DOOM na Pico
Obwód jest gotowy: kolorowy wyświetlacz **TFT 320×240** na SPI (ILI9341: SCK GP18, MOSI GP19, CS GP17, DC GP20,
RESET GP21, podświetlenie GP22) i osiem przycisków. Brakuje programu — i to już twoja robota: **prawdziwy Doom**
(shareware'owy DOOM1.WAD, epizod pierwszy) to nie szkic, tylko gotowy obraz flasha, jak plik UF2 przeciągany
na prawdziwe Pico.

1. **Zbuduj go**: w repozytorium Electro `apps/notebook/scripts/make-pico-doom.sh doom.bin` (potrzebne git i
   nix). Skrypt bierze port [kilograham/rp2040-doom](https://github.com/kilograham/rp2040-doom), wyświetlacz z
   [pondahai/rp2040-doom-ili9341](https://github.com/pondahai/rp2040-doom-ili9341) i małą łatkę pod emulator
   (bez dźwięku, klatki przez DMA).
2. **Wgraj go**: zaznacz płytkę i kliknij **Wgraj plik .uf2 / .bin** — albo po prostu upuść plik na płytkę.
   Plik zapisze się w notatce, a pierwsza linia programu płytki będzie na niego wskazywać.
3. Uruchom symulację (⚡). Po chwili ekran tytułowy i demo; **kliknij schemat** i graj z klawiatury:
   **Enter** — menu i wybór (New Game), **strzałki** — ruch, **Ctrl** — strzał, **spacja** — drzwi, **Esc** — menu.

Doom zbudowany bez łatki też ruszy, tylko kilka razy za wolno: gra muzykę przez PIO, czego emulator nie liczy
tanio. Gdy komputer nie nadąża, rdzenie zwalniają — o ile, widać przy płytce (np. **PICO_1 · 150 MHz**).
""")
DOOM = """// Tu przyjdzie Doom: zbuduj doom.bin (apps/notebook/scripts/make-pico-doom.sh) i wgraj go —
// zaznacz płytkę → „Wgraj plik .uf2 / .bin” albo upuść plik na płytkę. Ten szkic zostanie pod linią z plikiem.
// TFT: SCK GP18, MOSI GP19, CS GP17, DC GP20, RESET GP21, podświetlenie GP22.
// Przyciski do GND: ↑ GP9, ↓ GP5, ← GP8, → GP6, strzał GP3, użyj GP2, Enter GP4, menu GP28.

void setup() {}

void loop() {}
"""
d = Drawing()
d.add("PICO_1", "pico", (0, 0), 0, None, DOOM)
d.add("TFT_1", "ili9341", (16, 6), 0)
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
tft = {"3V3": 0, "GND": 1, "cs": 2, "rst": 3, "dc": 4, "mosi": 5, "sck": 6, "bl": 7}
d.connect(
    {
        "cs": [PI("GP17"), ("TFT_1", tft["cs"])],
        "rst": [PI("GP21"), ("TFT_1", tft["rst"])],
        "dc": [PI("GP20"), ("TFT_1", tft["dc"])],
        "mosi": [PI("GP19"), ("TFT_1", tft["mosi"])],
        "sck": [PI("GP18"), ("TFT_1", tft["sck"])],
        "bl": [PI("GP22"), ("TFT_1", tft["bl"])],
        **{f"key_{pin}": [PI(pin), (f"B_{k + 1}", 0)] for k, pin in enumerate(keys)},
        "3V3": [PI("3V3"), ("TFT_1", tft["3V3"])],
        "GND": [PI("GND"), ("TFT_1", tft["GND"]), *[(f"B_{k + 1}", 1) for k in range(len(keys))]],
    }
)
d.cell("pico_doom")

md("""
## W kodzie
Każdy z tych elementów jest też w Pythonie — `code()` zapisze schemat jako kod:
`Photoresistor(10000, lux=100)`, `Thermistor(10000, temperature=25)`, `Zener(5.1)`, `NMOS()`, `VCVS(10)`,
`Servo()`, `Buzzer()`, `PassiveBuzzer()`, `RGBLED()`, `SevenSegment()`, `LCD1602()`, `Ultrasonic(distance=80)`,
`LCD1602I2C()`, `SSD1306()`, `ILI9341()`, `DS1307()`, `Pico()`.
""")
code("""
code(czujniki)
""")

now = datetime.now(timezone.utc).isoformat(timespec="seconds")
notebook = {
    "format": "electro-notebook",
    "version": 2,
    "id": secrets.token_hex(8),
    "title": "Nowe elementy",
    "created": now,
    "modified": now,
    "settings": {"codeInPdf": True},
    "cells": cells,
}
path = Path(__file__).parent.parent / "examples/nowe-elementy.electro.json"
path.write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(path)
