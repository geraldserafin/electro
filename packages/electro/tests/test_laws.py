"""One form of law for every element (DESIGN.md §13): none needs anything new."""

import math

import pytest
import sympy as sp
from electro import (
    GND,
    VCVS,
    Current,
    D,
    Element,
    I,
    Inductor,
    Node,
    Norator,
    Nullator,
    Resistor,
    V,
    Voltage,
    VoltageSource,
)
from electro.algebra import Origin
from electro.laws import is_source, reading, stores


def test_steps_say_where_each_value_comes_from():
    e, r1, r2 = (VoltageSource("E"), Resistor("R_1"), Resistor("R_2"))
    a = Node("A")
    s = ((GND >> e >> a) @ (a >> r1 >> GND) @ (a >> r2 >> GND)).final({e: 12, r1: 4, r2: 6})
    first = s.steps[0]
    assert first.found == (sp.Symbol("V_A"),) and first.values == (12,)
    assert first.because == (Origin("law", e, 0),)
    by = {x: step.because for step in s.steps for x in step.found}
    assert by[sp.Symbol("I_R_1")] == (Origin("law", r1, 0),) and by[sp.Symbol("I_R_2")] == (Origin("law", r2, 0),)
    assert by[sp.Symbol("I_E")][0].what == "kcl"
    assert s(I(e)) == 5


def test_a_four_terminal_element_a_voltage_controlled_source():
    e, r, amp = (VoltageSource("E"), Resistor("R"), VCVS("mu"))
    a, out = (Node("A"), Node("OUT"))
    circuit = (GND >> e >> a) @ (amp >> a @ GND @ GND @ out) @ (out >> r >> GND)
    s = circuit.final({e: 2, r: 100, "mu": 10})
    assert s(V(out)) == 20 and s(I(amp, "cp")) == 0
    assert not is_source(amp) and is_source(e)


def test_what_a_kind_is_follows_from_its_laws():
    from electro.elements import ALL
    from electro.elements import BY_KIND as BY_NAME

    sources = {k.kind for k in ALL if len(k.terminals) == 2 and is_source(k())}
    assert sources == {"voltage_source", "current_source", "sine_source", "square_source"}
    assert {k.kind: reading(k()) for k in ALL if reading(k())} == {
        "wire": Current,
        "ammeter": Current,
        "open": Voltage,
        "voltmeter": Voltage,
    }
    assert stores(BY_NAME["capacitor"]()) and stores(BY_NAME["inductor"]()) and (not stores(BY_NAME["resistor"]()))


def test_a_nullor_two_laws_and_none_an_inverting_amplifier_from_it_and_two_resistors():
    e, r1, r2 = (VoltageSource("E"), Resistor("R_1"), Resistor("R_2"))
    n, out = (Node("N"), Node("OUT"))
    circuit = (
        (GND >> e >> Node("IN") >> r1 >> n) @ (n >> r2 >> out) @ (n >> Nullator() >> GND) @ (out >> Norator() >> GND)
    )
    s = circuit.final({e: 1, r1: 1000, r2: 4700})
    assert s(V(out)) == sp.Rational(-47, 10)


def test_an_inner_quantity_an_inductor_written_by_its_flux_is_the_inductor():

    class FluxInductor(Element):
        kind, prefix, terminals = ("flux_inductor", "L", ("a", "b"))

        def laws(self, t, p):
            phi = t.inner("phi")
            return [t.across("a", "b") - D(phi), phi - p[""] * t.I["a"]]

    currents = []
    for kind in (Inductor, FluxInductor):
        e, r, coil = (VoltageSource("E"), Resistor("R"), kind("L"))
        circuit, values = (GND >> e >> r >> Node() >> coil >> GND, {e: 10, r: 10, coil: 1})
        currents.append(circuit.simulate(values, until=0.3, dt=0.001).at(I(coil), 0.1))
    assert currents == pytest.approx([1 - math.exp(-1)] * 2, abs=0.01)
