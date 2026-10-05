"""One form of law for every element (DESIGN.md §13): none needs anything new."""

import math
from collections.abc import Mapping

import pytest
import sympy as sp
from electro.core import (
    GND,
    VCVS,
    D,
    I,
    Inductor,
    Kind,
    Node,
    Norator,
    Nullator,
    Origin,
    Problem,
    Resistor,
    Terminals,
    V,
    VoltageSource,
    at,
    is_source,
    simulate,
    solve,
)


def test_steps_say_where_each_value_comes_from():
    e, r1, r2 = VoltageSource("E"), Resistor("R_1"), Resistor("R_2")
    a = Node("A")
    s = solve(Problem((GND >> e >> a) @ (a >> r1 >> GND) @ (a >> r2 >> GND), {e: 12, r1: 4, r2: 6}))
    first = s.steps[0]
    assert first.found == (sp.Symbol("V_A"),) and first.values == (12,)
    assert first.because == (Origin("law", e, 0),)
    by = {x: step.because for step in s.steps for x in step.found}
    assert by[sp.Symbol("I_R_1")] == (Origin("law", r1, 0),) and by[sp.Symbol("I_R_2")] == (Origin("law", r2, 0),)
    assert by[sp.Symbol("I_E")][0].what == "kcl"
    assert s(I(e)) == 5


def test_a_four_terminal_element_a_voltage_controlled_source():
    e, r, amp = VoltageSource("E"), Resistor("R"), VCVS("mu")
    a, out = Node("A"), Node("OUT")
    circuit = (GND >> e >> a) @ at(amp, a, GND, GND, out) @ (out >> r >> GND)
    s = solve(Problem(circuit, {e: 2, r: 100, "mu": 10}))
    assert s(V(out)) == 20 and s(I(amp, "cp")) == 0
    assert not is_source(amp) and is_source(e)


def test_a_nullor_two_laws_and_none_an_inverting_amplifier_from_it_and_two_resistors():
    e, r1, r2 = VoltageSource("E"), Resistor("R_1"), Resistor("R_2")
    n, out = Node("N"), Node("OUT")
    circuit = (
        (GND >> e >> Node("IN") >> r1 >> n) @ (n >> r2 >> out) @ (n >> Nullator() >> GND) @ (out >> Norator() >> GND)
    )
    s = solve(Problem(circuit, {e: 1, r1: 1000, r2: 4700}))
    assert s(V(out)) == sp.Rational(-47, 10)


def test_an_inner_quantity_an_inductor_written_by_its_flux_is_the_inductor():
    def flux(t: Terminals, p: Mapping[str, sp.Symbol]) -> list[sp.Expr]:
        phi = t.inner("phi")
        return [t.V["a"] - t.V["b"] - D(phi), phi - p[""] * t.I["a"]]

    FluxInductor = Kind("flux_inductor", "L", ("a", "b"), flux)
    currents = []
    for kind in (Inductor, FluxInductor):
        e, r, coil = VoltageSource("E"), Resistor("R"), kind("L")
        p = Problem(GND >> e >> r >> Node() >> coil >> GND, {e: 10, r: 10, coil: 1})
        currents.append(simulate(p, until=0.3, dt=1e-3)(I(coil))(0.1))
    assert currents[0] == pytest.approx(currents[1]) and currents[0] == pytest.approx(1 - math.exp(-1), abs=0.01)
