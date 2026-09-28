"""Simulation in time: the step-by-step results against what the textbook says."""

import math

import pytest

from electro import (
    LED, NPN, Arduino, Button, Capacitor, Inductor, Potentiometer, Resistor, Switch, Timer555, VoltageSource,
    code, ground, net, node, simulate, supply,
)
from electro.issues import NeedsSimulation, NoSuchInput, ValueNeeded
from electro.sim import compile_sim


def test_rc_charges_like_the_exponential():
    trace = simulate(supply(5) + Resistor(1000) + node("A") + Capacitor(1e-3) + ground, t=5)
    for t in (0.5, 1, 2, 5):
        assert trace.at(t)["V_A"] == pytest.approx(5 * (1 - math.exp(-t)), abs=0.05)


def test_rl_current_rises_like_the_exponential():
    trace = simulate(supply(10) + Resistor(10) + Inductor(1) + ground, t=0.5)  # τ = L/R = 0.1 s
    assert trace.at(0.1)["I_L_1"] == pytest.approx(1 - math.exp(-1), abs=0.02)
    assert trace.at(0.5)["I_L_1"] == pytest.approx(1, abs=0.02)


def test_led_with_its_resistor():
    trace = simulate(supply(5) + Resistor(150) + LED() + ground, t=1e-3)
    end = trace.at(1e-3)
    assert end["U_LED_1"] == pytest.approx(2.0, abs=0.02)  # red: 2 V at 20 mA
    assert end["I_LED_1"] == pytest.approx(0.02, abs=5e-4)
    blue = simulate(supply(5) + Resistor(150) + LED("blue") + ground, t=1e-3).at(1e-3)
    assert blue["U_LED_1"] > 3


def test_555_astable_blinks_at_the_textbook_period():
    astable = net(
        (VoltageSource(9), "GND", "vcc"),
        (Timer555(), "GND", "tc", "out", "vcc", "ctrl", "tc", "dis", "vcc"),
        (Resistor(1000), "vcc", "dis"), (Resistor(10000), "dis", "tc"),
        (Capacitor(100e-6), "tc", "GND"),
        (Resistor(330), "out", "a"), (LED("green"), "a", "GND"),
    )
    trace = simulate(astable, t=5)
    out = trace.V("out")
    rising = [trace.t[i] for i in range(1, len(out)) if out[i - 1] < 4 <= out[i]]
    period = rising[2] - rising[1]
    assert period == pytest.approx(0.693 * (1000 + 2 * 10000) * 100e-6, rel=0.05)
    settled = trace.V("tc")[len(out) // 2:]
    assert min(settled) == pytest.approx(3, abs=0.1) and max(settled) == pytest.approx(6, abs=0.1)  # ⅓, ⅔ of 9 V


def test_two_transistor_multivibrator_takes_turns():
    multi = net(
        (VoltageSource(9), "GND", "vcc"),
        (Resistor(470), "vcc", "a1"), (LED("red"), "a1", "c1"),
        (Resistor(470), "vcc", "a2"), (LED("green"), "a2", "c2"),
        (Resistor(47000), "vcc", "b2"), (Resistor(47000), "vcc", "b1"),
        (Capacitor(47e-6), "c1", "b2"), (Capacitor(33e-6), "c2", "b1"),
        (NPN(), "b1", "c1", "GND"), (NPN(), "b2", "c2", "GND"),
    )
    trace = simulate(multi, t=3.5)
    # at first both conduct while the capacitors charge; then they take turns
    lit = [(s["I_LED_1"] > 0.005, s["I_LED_2"] > 0.005) for s in map(trace.at, (1.25, 1.75, 2.25, 2.75, 3.25))]
    assert sum(a != b for a, b in lit) >= 4  # (nearly) always exactly one lit
    assert {(True, False), (False, True)} <= set(lit)  # and both get a turn


def test_arduino_pins_switches_and_potentiometer():
    board = net(
        (Arduino(), *[f"d{i}" for i in range(14)], *[f"a{i}" for i in range(6)], "5V", "GND"),
        (Resistor(220), "d13", "x"), (LED(), "x", "GND"),
        (Button(), "d2", "GND"),
        (Potentiometer(10000), "5V", "GND", "a0"),
    )
    trace = simulate(board, t=2, dt=0.01, inputs={
        "ARD_1.D13": lambda t: "high" if t % 1 < 0.5 else "low",
        "ARD_1.D2": "pullup",
        "B_1": lambda t: t > 1.5,
        "P_1": 0.25,
    })
    assert trace.at(0.2)["I_LED_1"] == pytest.approx(0.0124, abs=5e-4)  # (5 − 2) V / (220 + 25) Ω
    assert trace.at(0.7)["I_LED_1"] == pytest.approx(0, abs=1e-6)
    assert trace.at(1.2)["V_d2"] == pytest.approx(5, abs=0.01)  # pulled up
    assert trace.at(1.7)["V_d2"] == pytest.approx(0, abs=0.01)  # the button pressed
    assert trace.at(1)["V_a0"] == pytest.approx(3.75, abs=0.01)  # a quarter of the way from 5 V
    with pytest.raises(NoSuchInput):
        simulate(board, t=0.1, inputs={"S_9": 1})


def test_on_paper_switches_work_and_semiconductors_ask_for_a_simulation():
    closed = (supply(5) + Resistor(100) + Switch(closed=True) + Resistor(100) + ground).solve()
    assert closed["R_1"].I == pytest.approx(0.025)
    with pytest.raises(NeedsSimulation):
        (supply(5) + Resistor(100) + LED() + ground).solve()
    with pytest.raises(ValueNeeded):
        compile_sim(supply(5) + Resistor() + ground)


def test_code_writes_the_new_elements_back():
    c = supply(5) + Resistor(100) + LED("green") + Switch(closed=True) + ground
    assert "LED('green')" in code(c) and "Switch(closed=True)" in code(c)
    scope: dict = {}
    exec("from electro import *\n" + code(c), scope)
    assert code(scope["uklad"]) == code(c)


def test_the_program_in_javascript_is_the_same_program():
    program = compile_sim(supply(5) + Resistor(150) + LED() + ground)
    data = program.to_json()
    assert "limexp(" in data and "F[" in data and "J[" in data
