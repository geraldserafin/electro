"""Writes src/features/simulation/fixtures/*.live.json: circuits compiled for the page's engine, as
kernel.live() would give them, for session.test.ts. Run from the repo root with PYTHONPATH set (e.g.
in devenv shell) after changing how electro compiles a circuit in time.
"""
import json
from pathlib import Path

from electro import Arduino, Ultrasonic, VoltageSource, net
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
