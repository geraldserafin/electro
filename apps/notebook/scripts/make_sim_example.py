"""Builds apps/notebook/examples/symulacja-w-czasie.electro.json: circuits that live in time — an LED
with a switch, a 555 blinker, an Arduino running a sketch — and simulate() in code (run from the
repo root with PYTHONPATH set, e.g. in devenv shell)."""

import json
import secrets
from datetime import datetime, timezone
from pathlib import Path

from electro_schematic import Element, Schematic, Wire

cells = []
md = lambda text: cells.append({"id": secrets.token_hex(4), "type": "markdown", "source": text.strip()})
code = lambda text: cells.append({"id": secrets.token_hex(4), "type": "code", "source": text.strip(), "outputs": []})


def drawing(name, elements, wires):
    sch = Schematic([Element(*e) for e in elements], [Wire(w) for w in wires])
    sch.to_circuit()  # it must be a circuit
    cells.append(
        {"id": secrets.token_hex(4), "type": "schematic", "name": name, "schematic": json.loads(sch.to_json())}
    )


md("""
Obwód z diodą, tranzystorem albo układem scalonym nie jest liniowy — nie rozwiązuje się go na papierze,
tylko **w czasie**: krok po kroku, jak w symulatorze. Pod każdym schematem jest przycisk **▶ Symuluj w czasie**.
Przewody zmieniają kolor z napięciem (zielony: dodatnie), diody świecą, łączniki przełączasz kliknięciem,
a przyciski działają, dopóki je przytrzymujesz. Oscyloskop pod schematem pokazuje przebiegi.
""")

md("## 1. Dioda i łącznik\nKliknij łącznik $S_1$ w czasie symulacji.")
drawing(
    "dioda",
    [
        ("E_1", "voltage_source", (0, 8), 270, "5"),
        ("R_1", "resistor", (4, 0), 0, "150"),
        ("LED_1", "led", (12, 2), 90, None, "green"),
        ("S_1", "switch", (8, 8), 180, None, "closed"),
        ("gnd", "ground", (0, 8), 0),
    ],
    [
        [(0, 4), (0, 0), (4, 0)],
        [(8, 0), (12, 0), (12, 2)],
        [(12, 6), (12, 8), (8, 8)],
        [(4, 8), (0, 8)],
    ],
)

md("""
## 2. Migacz na NE555
Kondensator $C_1$ ładuje się przez $R_1 + R_2$ do ⅔ napięcia zasilania i rozładowuje przez $R_2$ do ⅓ —
wyjście (pin 3) przełącza się za każdym razem. Okres $T \\approx 0{,}693\\,(R_1 + 2R_2)\\,C_1 \\approx 1{,}5$ s.
""")
drawing(
    "migacz",
    [
        ("E_1", "voltage_source", (0, 14), 270, "9"),
        ("IC_1", "timer555", (10, 2), 0),
        ("R_1", "resistor", (6, 0), 90, "1k"),
        ("R_2", "resistor", (6, 6), 90, "10k"),
        ("C_1", "capacitor", (6, 10), 90, "100u"),
        ("C_2", "capacitor", (14, 8), 90, "10n"),
        ("R_3", "resistor", (16, 5), 0, "330"),
        ("LED_1", "led", (20, 5), 90, None, "red"),
        ("gnd", "ground", (0, 14), 0),
    ],
    [
        [(0, 10), (0, 0), (6, 0)],
        [(6, 0), (12, 0)],
        [(12, 0), (14, 0)],  # + rail
        [(12, 2), (12, 0)],
        [(14, 2), (14, 0)],  # vcc, reset
        [(6, 4), (6, 6)],
        [(6, 6), (10, 6)],  # R1 – dis – R2
        [(10, 4), (9, 4), (9, 5), (10, 5)],
        [(6, 10), (9, 10), (9, 5)],  # trig = thr = the capacitor
        [(0, 14), (6, 14)],
        [(6, 14), (12, 14)],
        [(12, 14), (14, 14)],
        [(14, 14), (20, 14)],  # ground rail
        [(12, 8), (12, 14)],
        [(14, 12), (14, 14)],
        [(20, 9), (20, 14)],
    ],
)

md("""
## 3. Arduino
Szkic działa na emulowanym ATmega328P (jak w prawdziwym Arduino Uno): dioda na pinie 13 miga, a gdy
przytrzymasz przycisk na pinie 2, miga szybciej. `analogRead(A0)` czyta napięcie z suwaka potencjometru —
zmień jego położenie w panelu elementu i patrz na monitor portu szeregowego pod schematem.
Szkic kompiluje przeglądarka (za pierwszym razem pobiera kompilator), bez logowania.
""")
SKETCH = """// Dioda na pinie 13 miga; przycisk na pinie 2 (do masy) przyspiesza ją.
// Na porcie szeregowym: napięcie z potencjometru na A0.
void setup() {
  pinMode(13, OUTPUT);
  pinMode(2, INPUT_PULLUP);
  Serial.begin(9600);
}

void loop() {
  int ms = digitalRead(2) == LOW ? 100 : 500;
  blink(ms);
  Serial.print("A0 = ");
  Serial.print(analogRead(A0) * 5.0 / 1023);
  Serial.println(" V");
}

void blink(int ms) {
  digitalWrite(13, HIGH);
  delay(ms);
  digitalWrite(13, LOW);
  delay(ms);
}
"""
drawing(
    "arduino",
    [
        ("ARD_1", "arduino", (0, 0), 0, None, SKETCH),
        ("R_1", "resistor", (2, 0), 270, "220"),
        ("LED_1", "led", (5, -6), 0, None, "yellow"),
        ("gnd1", "ground", (9, -6), 0),
        ("B_1", "button", (14, 0), 270),
        ("gnd2", "ground", (16, -4), 0),
        ("P_1", "potentiometer", (7, 10), 0, "10k", "0.3"),
        ("gnd3", "ground", (5, 8), 0),
        ("gnd4", "ground", (13, 10), 0),
    ],
    [
        [(2, -4), (2, -6), (5, -6)],
        [(14, -4), (16, -4)],
        [(7, 10), (3, 10), (3, 8)],
        [(11, 10), (13, 10)],
    ],
)

md("""
## 4. W kodzie: `simulate()`
To samo z kodu: `simulate(układ, t=…)` zwraca przebiegi — narysowane pod komórką, a liczby w `trace["V_A"]`,
`trace.at(t)`. Multiwibrator na dwóch tranzystorach: diody świecą na zmianę.
""")
code("""
multiwibrator = net(
    (VoltageSource(9), "GND", "vcc"),
    (Resistor(470), "vcc", "a1"), (LED("red"), "a1", "c1"),
    (Resistor(470), "vcc", "a2"), (LED("green"), "a2", "c2"),
    (Resistor(47000), "vcc", "b2"), (Resistor(47000), "vcc", "b1"),
    (Capacitor(47e-6), "c1", "b2"), (Capacitor(33e-6), "c2", "b1"),
    (NPN(), "b1", "c1", "GND"), (NPN(), "b2", "c2", "GND"),
)
przebieg = simulate(multiwibrator, t=6)
przebieg.plot("I_LED_1", "I_LED_2", "V_b1")
""")
code("""
# schematy z komórek też: migacz z punktu 2
simulate(migacz, t=5).plot("U_C_1", "I_LED_1")
""")

now = datetime.now(timezone.utc).isoformat(timespec="seconds")
notebook = {
    "format": "electro-notebook",
    "version": 2,
    "id": secrets.token_hex(8),
    "title": "Symulacja w czasie",
    "created": now,
    "modified": now,
    "settings": {"codeInPdf": True},
    "cells": cells,
}
path = Path(__file__).parent.parent / "examples/symulacja-w-czasie.electro.json"
path.write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(path)
