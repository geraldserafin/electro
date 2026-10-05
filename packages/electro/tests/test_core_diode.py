"""The first law beyond algebra, a diode: Newton, with no trick of its own."""

import math

import pytest
from electro.core import (
    GND,
    V_T,
    Capacitor,
    Diode,
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


def _bisect(f, lo: float, hi: float) -> float:
    for _ in range(200):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if f(lo) * f(mid) > 0 else (lo, mid)
    return (lo + hi) / 2


def test_a_diode_forward_its_drop_as_shockley_and_ohm_have_it():
    e, r, d = VoltageSource("E"), Resistor("R"), Diode("D")
    s = solve(Problem(GND >> e >> r >> Node() >> d >> GND, {e: 5, r: 1000}))
    vt, i_s = float(V_T), 1e-14
    drop = _bisect(lambda u: (5 - u) / 1000 - i_s * (math.exp(u / vt) - 1), 0, 1)
    assert float(s(U(d))) == pytest.approx(drop, abs=1e-9)
    assert float(s(I(d))) == pytest.approx((5 - drop) / 1000, rel=1e-9)
    assert s.steps[0].how == "numerically"


def test_a_diode_backwards_lets_through_only_its_saturation_current():
    e, r, d = VoltageSource("E"), Resistor("R"), Diode("D")
    b = Node()
    s = solve(Problem((GND >> e >> r >> b) @ at(d, GND, b), {e: 5, r: 1000}))
    assert float(s(I(d))) == pytest.approx(-1e-14, rel=1e-6)


def test_a_diodes_own_parameters_are_data():
    e, r, d = VoltageSource("E"), Resistor("R"), Diode("D")
    s = solve(Problem(GND >> e >> r >> Node() >> d >> GND, {e: 5, r: 1000, d: {"I_S": "1e-12", "n": 2}}))
    vt = float(V_T)
    drop = _bisect(lambda u: (5 - u) / 1000 - 1e-12 * (math.exp(u / (2 * vt)) - 1), 0, 2)
    assert float(s(U(d))) == pytest.approx(drop, abs=1e-9)


def test_with_a_diode_too_the_paper_is_where_time_settles():
    e, r1, r2, d, c = VoltageSource("E"), Resistor("R_1"), Resistor("R_2"), Diode("D"), Capacitor("C")
    b, out = Node("B"), Node("OUT")
    circuit = (GND >> e >> r1 >> b >> d >> out) @ (out >> r2 >> GND) @ (out >> c >> GND)
    p = Problem(circuit, {e: 5, r1: 100, r2: 1000, c: "10u"})
    settled = simulate(p, until=0.02, dt=2e-5).at(V(out), 0.02)
    assert settled == pytest.approx(float(solve(p)(V(out))), rel=1e-4)


def test_diodes_in_a_bridge_and_one_beyond_reason_newton_gets_there_without_a_trick():
    e, r, rg = VoltageSource("E"), Resistor("R"), Resistor("R_g")
    d1, d2, d3, d4 = (Diode(f"D{k}") for k in range(1, 5))
    p, n, a, b = Node("P"), Node("N"), Node("A"), Node("B")
    bridge = (
        (n >> e >> p) @ at(d1, p, a) @ at(d2, n, a) @ at(d3, b, p) @ at(d4, b, n) @ (a >> r >> b) @ (n >> rg >> GND)
    )
    s = solve(Problem(bridge, {e: 10, r: 1000, rg: 10**6}))
    assert float(s(I(r))) == pytest.approx(8.579e-3, rel=1e-3)
    s = solve(Problem(GND >> e >> d1 >> GND, {e: 5}))
    assert math.log10(float(s(I(d1)))) == pytest.approx(69.996, abs=1e-3)
