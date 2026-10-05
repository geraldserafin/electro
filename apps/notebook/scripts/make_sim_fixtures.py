"""Writes src/features/simulation/fixtures/*.live.json: circuits compiled for the page's engine, as
kernel.live() would give them, for session.test.ts. Run from the repo root with PYTHONPATH set (e.g.
in devenv shell) after changing how electro compiles a circuit in time.
"""

import json
from pathlib import Path

from electro import Arduino, Pico, compile_program
from electro.problem.netlist import from_netlist

here = Path(__file__).parent.parent / "src/features/simulation/fixtures"
ARDUINO_PINS = Arduino.terminals[:-2]
PICO_PINS = Pico.terminals[:-3]


def element(id: str, kind: str, *nodes: str, value=None, **params) -> dict:
    return {"id": id, "kind": kind, "nodes": list(nodes), "value": value, "params": params}


def write(name: str, elements: list[dict], pins: dict | None = None) -> None:
    program = json.loads(compile_program(from_netlist({"elements": elements}).problem).to_json())
    data = program if pins is None else {"program": program, "wires": [], "pins": pins}
    (here / name).write_text(json.dumps(data) + "\n")
    print(here / name)


def board(pins: tuple[str, ...], wiring: dict[str, str], *rest: str) -> list[str]:
    return [wiring.get(pin, f"free_{pin}") for pin in pins] + list(rest)


def drawn(pins: tuple[str, ...], wiring: dict[str, str], *rest: str) -> list:
    return [wiring.get(pin) for pin in pins] + list(rest)


# an HC-SR04 on an Uno: trigger on D9, echo on D10, powered from the board's 5 V
wiring = {"D9": "trig", "D10": "echo"}
write(
    "sonar.live.json",
    [
        element("ARD_1", "arduino", *board(ARDUINO_PINS, wiring, "vcc", "GND")),
        element("US_1", "ultrasonic", "vcc", "trig", "echo", "GND"),
    ],
    {"ARD_1": drawn(ARDUINO_PINS, wiring, "vcc", "GND"), "US_1": ["vcc", "trig", "echo", "GND"]},
)

# I²C on an Uno: an LCD and an OLED on A4/A5 (the OLED's pins: SCL before SDA), a clock on the wrong pins
wiring = {"A4": "sda", "A5": "scl", "D2": "d2", "D3": "d3"}
write(
    "i2c.live.json",
    [
        element("ARD_1", "arduino", *board(ARDUINO_PINS, wiring, "vcc", "GND")),
        element("LCD_1", "lcd1602_i2c", "GND", "vcc", "sda", "scl"),
        element("OLED_1", "ssd1306", "GND", "vcc", "scl", "sda"),
        element("RTC_1", "ds1307", "GND", "vcc", "d2", "d3"),
    ],
    {
        "ARD_1": drawn(ARDUINO_PINS, wiring, "vcc", "GND"),
        "LCD_1": ["GND", "vcc", "sda", "scl"],
        "OLED_1": ["GND", "vcc", "scl", "sda"],
        "RTC_1": ["GND", "vcc", "d2", "d3"],
    },
)

# a Pico (fixtures/blink.pico.ino): an LED on GP15 through 220 Ω, a potentiometer on GP26 across its 3V3
wiring = {"GP15": "led", "GP26": "wiper"}
write(
    "pico.live.json",
    [
        element("PICO_1", "pico", *board(PICO_PINS, wiring, "vbus", "v33", "GND")),
        element("R_1", "resistor", "led", "a", value=220),
        element("LED_1", "led", "a", "GND"),
        element("P_1", "potentiometer", "v33", "GND", "wiper", value=10000, position=0.25),
    ],
    {"PICO_1": drawn(PICO_PINS, wiring, "vbus", "v33", "GND")},
)

# Doom's wiring (github.com/geraldserafin/electro-doom): an ILI9341 on SPI0 — SCK GP18, MOSI GP19, CS GP17, DC
# GP20, RESET GP21, the backlight GP22 — powered from the Pico's 3V3; the buttons' pins left open
wiring = {"GP17": "cs", "GP18": "sck", "GP19": "mosi", "GP20": "dc", "GP21": "rst", "GP22": "bl"}
write(
    "tft.live.json",
    [
        element("PICO_1", "pico", *board(PICO_PINS, wiring, "vbus", "v33", "GND")),
        element("TFT_1", "ili9341", "v33", "GND", "cs", "rst", "dc", "mosi", "sck", "bl", "miso"),
    ],
    {
        "PICO_1": drawn(PICO_PINS, wiring, "vbus", "v33", "GND"),
        "TFT_1": ["v33", "GND", "cs", "rst", "dc", "mosi", "sck", "bl", "miso"],
    },
)

# a stress test (engine.test.ts): 40 RC stages, 80 elements, charged from 5 V
stages = [element("E_1", "voltage_source", "GND", "n0", value=5)]
for k in range(40):
    stages += [
        element(f"R_{k + 1}", "resistor", f"n{k}", f"n{k + 1}", value=100),
        element(f"C_{k + 1}", "capacitor", f"n{k + 1}", "GND", value="1u"),
    ]
stages.append(element("R_41", "resistor", "n40", "GND", value=100))
write("ladder.live.json", stages)
