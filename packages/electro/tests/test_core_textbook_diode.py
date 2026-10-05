"""An element of several ways, the textbook's diode: assume, solve, check, as by hand."""

import pytest
import sympy as sp
from electro.core import (
    GND,
    Capacitor,
    Diode,
    DiodeDrop,
    I,
    Node,
    Problem,
    Resistor,
    U,
    V,
    VoltageSource,
    at,
    simulate,
    solve,
)


def test_the_textbook_diode_assumed_on_checked_and_its_steps_say_so():
    e, r, d = VoltageSource("E"), Resistor("R"), DiodeDrop("D")
    s = solve(Problem(GND >> e >> r >> Node() >> d >> GND, {e: 5, r: 1000}))
    assert s(U(d)) == sp.Rational(7, 10) and s(I(d)) == sp.Rational(43, 10000)
    hows = [step.how for step in s.steps]
    assert hows[0] == "assumed" and s.steps[0].because[0].case == "on" and hows[-1] == "checked"


def test_the_textbook_diode_backwards_on_rejected_then_off():
    e, r, d = VoltageSource("E"), Resistor("R"), DiodeDrop("D")
    b = Node()
    s = solve(Problem((GND >> e >> r >> b) @ at(d, GND, b), {e: 5, r: 1000}))
    assert s(I(d)) == 0 and s(U(d)) == -5
    tries = [(step.how, step.because[0].case) for step in s.steps if step.how in ("assumed", "rejected", "checked")]
    assert tries == [("assumed", "on"), ("rejected", "on"), ("assumed", "off"), ("checked", "off")]


def test_textbook_and_shockley_differ_by_little_and_four_textbook_diodes_make_a_bridge():
    def drop(kind) -> float:
        e, r, d = VoltageSource("E"), Resistor("R"), kind("D")
        return float(solve(Problem(GND >> e >> r >> Node() >> d >> GND, {e: 5, r: 1000}))(I(d)))

    assert drop(DiodeDrop) == pytest.approx(drop(Diode), rel=0.02)
    e, r, rg = VoltageSource("E"), Resistor("R"), Resistor("R_g")
    d1, d2, d3, d4 = (DiodeDrop(f"D{k}") for k in range(1, 5))
    p, n, a, b = Node("P"), Node("N"), Node("A"), Node("B")
    bridge = (
        (n >> e >> p) @ at(d1, p, a) @ at(d2, n, a) @ at(d3, b, p) @ at(d4, b, n) @ (a >> r >> b) @ (n >> rg >> GND)
    )
    assert solve(Problem(bridge, {e: 10, r: 1000, rg: 10**6}))(I(r)) == sp.Rational(86, 10000)


def test_in_time_each_step_keeps_its_way_while_it_holds_and_settles_on_the_paper():
    e, r1, r2, d, c = VoltageSource("E"), Resistor("R_1"), Resistor("R_2"), DiodeDrop("D"), Capacitor("C")
    b, out = Node("B"), Node("OUT")
    p = Problem(
        (GND >> e >> r1 >> b >> d >> out) @ (out >> r2 >> GND) @ (out >> c >> GND), {e: 5, r1: 100, r2: 1000, c: "10u"}
    )
    assert simulate(p, until=0.02, dt=2e-5)(V(out))(0.02) == pytest.approx(float(solve(p)(V(out))), rel=1e-4)
