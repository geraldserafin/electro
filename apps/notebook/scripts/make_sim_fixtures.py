"""Writes src/features/simulation/fixtures/*.live.json: circuits compiled for the page's engine, as
kernel.live() would give them, for session.test.ts. Run from the repo root with PYTHONPATH set (e.g.
in devenv shell) after changing how electro compiles a circuit in time.
"""
import json
from pathlib import Path

from electro import DS1307, LED, SSD1306, Arduino, LCD1602I2C, Pico, Potentiometer, Resistor, Ultrasonic, net
from electro.devices import ARDUINO_PINS
from electro.sim import compile_sim

here = Path(__file__).parent.parent / "src/features/simulation/fixtures"

# an HC-SR04 on an Uno: trigger on D9, echo on D10, powered from the board's 5 V
wiring = {"D9": "trig", "D10": "echo"}
board = [wiring.get(pin, f"free_{pin}") for pin in ARDUINO_PINS] + ["vcc", "GND"]
circuit = net((Arduino(), *board), (Ultrasonic(), "vcc", "trig", "echo", "GND"))
program = json.loads(compile_sim(circuit).to_json())
pins = {"ARD_1": [wiring.get(pin) for pin in ARDUINO_PINS] + ["vcc", "GND"], "US_1": ["vcc", "trig", "echo", "GND"]}
(here / "sonar.live.json").write_text(json.dumps({"program": program, "wires": [], "pins": pins}) + "\n")
print(here / "sonar.live.json")

# I²C on an Uno: an LCD and an OLED on A4/A5 (the OLED's pins: SCL before SDA), a clock on the wrong pins
wiring = {"A4": "sda", "A5": "scl", "D2": "d2", "D3": "d3"}
board = [wiring.get(pin, f"free_{pin}") for pin in ARDUINO_PINS] + ["vcc", "GND"]
circuit = net((Arduino(), *board), (LCD1602I2C(), "GND", "vcc", "sda", "scl"), (SSD1306(), "GND", "vcc", "scl", "sda"),
              (DS1307(), "GND", "vcc", "d2", "d3"))
program = json.loads(compile_sim(circuit).to_json())
pins = {"ARD_1": [wiring.get(pin) for pin in ARDUINO_PINS] + ["vcc", "GND"], "LCD_1": ["GND", "vcc", "sda", "scl"],
        "OLED_1": ["GND", "vcc", "scl", "sda"], "RTC_1": ["GND", "vcc", "d2", "d3"]}
(here / "i2c.live.json").write_text(json.dumps({"program": program, "wires": [], "pins": pins}) + "\n")
print(here / "i2c.live.json")

# a Pico (fixtures/blink.pico.ino): an LED on GP15 through 220 Ω, a potentiometer on GP26 across its 3V3
wiring = {"GP15": "led", "GP26": "wiper"}
board = [wiring.get(pin, f"free_{pin}") for pin in Pico.PINS] + ["vbus", "v33", "GND"]
circuit = net((Pico(), *board), (Resistor(220), "led", "a"), (LED(), "a", "GND"),
              (Potentiometer(10000, 0.25), "v33", "GND", "wiper"))
program = json.loads(compile_sim(circuit).to_json())
pins = {"PICO_1": [wiring.get(pin) for pin in Pico.PINS] + ["vbus", "v33", "GND"]}
(here / "pico.live.json").write_text(json.dumps({"program": program, "wires": [], "pins": pins}) + "\n")
print(here / "pico.live.json")
