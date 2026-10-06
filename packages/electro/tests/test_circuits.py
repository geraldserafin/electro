"""Circuits built of primitives, closed in any of the equivalent ways, and the problems set on them."""

import math

import pytest
import sympy as sp
from electro import (
    AC,
    GND,
    Capacitor,
    Element,
    ElementTwice,
    I,
    JoinsNodes,
    Node,
    NoSuchParameter,
    NotClosed,
    Parameter,
    Resistor,
    U,
    V,
    VoltageSource,
)


def test_a_loop_closed_by_one_node_its_two_ends_on_it():
    e, r1, r2 = (VoltageSource("E"), Resistor("R_1"), Resistor("R_2"))
    a = Node()
    loop_ = a >> e >> r1 >> r2 >> a
    assert loop_.free == (0, 0)
    s = loop_.final({e: 12, r1: 10, r2: 20})
    assert s(I(r1)) == sp.Rational(2, 5) and s(U(r2)) == 8


def test_closing_by_a_node_by_ground_and_by_cup_and_cap_is_the_same():

    def current(build):
        e, r = (VoltageSource("E"), Resistor("R"))
        return build(e, r).final({e: 10, r: 5})(I(r))

    a = Node()
    assert current(lambda e, r: a >> e >> r >> a) == 2
    assert current(lambda e, r: GND >> e >> r >> GND) == 2
    assert current(lambda e, r: ~(e >> r)) == 2


def test_parallel_by_shared_nodes_or_by_the_bar_is_the_same():

    def total(build):
        e, r1, r2 = (VoltageSource("E"), Resistor("R_1"), Resistor("R_2"))
        return build(e, r1, r2).final({e: 10, r1: 10, r2: 10})(I(e))

    a, b = (Node(), Node())
    assert total(lambda e, r1, r2: (a >> e >> b) @ (b >> r1 >> a) @ (b >> r2 >> a)) == 2
    assert total(lambda e, r1, r2: ~(e >> (r1 | r2))) == 2


def test_only_a_closed_circuit_is_a_problem_and_a_piece_says_how_many_ends_it_has_free():
    e, r = (VoltageSource("E"), Resistor("R"))
    assert (e >> r).free == (1, 1)
    with pytest.raises(NotClosed):
        (e >> r).final({e: 1, r: 1})


def test_series_never_glues_two_different_nodes_quietly():
    a, b = (Node(), Node())
    with pytest.raises(JoinsNodes):
        a >> VoltageSource("E1") >> Resistor("R1") >> a >> (b >> VoltageSource("E2") >> Resistor("R2") >> b)


def test_two_nodes_labelled_alike_are_still_two():
    e, r1, r2 = (VoltageSource("E"), Resistor("R_1"), Resistor("R_2"))
    b1, b2 = (Node("B"), Node("B"))
    s = (GND >> e >> b1 >> r1 >> b2 >> r2 >> GND).final({e: 12, r1: 10, r2: 20})
    assert s(V(b1)) == 12 and s(V(b2)) == 8


def test_one_element_is_in_one_place():
    r = Resistor("R")
    with pytest.raises(ElementTwice):
        GND >> VoltageSource("E") >> r >> r >> GND


def test_elements_named_alike_share_a_value_each_its_own_current():
    e, ra, rb = (VoltageSource("E"), Resistor("R"), Resistor("R"))
    s = (GND >> e >> ra >> Node() >> rb >> GND).final({"R": 50, e: 10})
    assert s(I(ra)) == s(I(rb)) == sp.Rational(1, 10) and s(U(ra)) == 5
    with pytest.raises(NoSuchParameter):
        (GND >> VoltageSource("E2") >> Resistor("R") >> GND).final({"R_9": 1})


def test_an_inverse_problem_a_current_given_a_resistance_found():
    e, r1, r2 = (VoltageSource("E"), Resistor("R_1"), Resistor("R_2"))
    circuit, values = (GND >> e >> r1 >> r2 >> GND, {e: 12, r1: 10, I(r1): "0.2"})
    assert circuit.final(values).answers(Parameter(r2)) == {Parameter(r2): 50}


def test_rc_on_paper_where_it_ends_in_time_how_it_gets_there_at_omega_its_phasor():
    e, r, c = (VoltageSource("E"), Resistor("R"), Capacitor("C"))
    b = Node("B")
    circuit, values = ((GND >> e >> r >> b) @ (b >> c >> GND), {e: 10, r: 1000, c: "100u"})
    assert circuit.final(values)(U(c)) == 10
    trace = circuit.simulate(values, until=0.5, dt=0.0001)
    assert abs(trace.at(U(c), 0.1) - 10 * (1 - math.exp(-1))) < 0.05
    phasor = circuit.final(values, AC(sp.Integer(10)))(U(c))
    assert abs(complex(phasor)) == pytest.approx(10 / math.sqrt(2))


def test_a_new_element_is_one_law_and_nothing_else():

    class Conductance(Element):
        kind, prefix, terminals = ("conductance", "G", ("a", "b"))

        def laws(self, t, p):
            return [t.I["a"] - p[""] * t.across("a", "b")]

    e, g = (VoltageSource("E"), Conductance("G"))
    circuit, values = (GND >> e >> g >> GND, {e: 10, g: "0.5"})
    assert circuit.final(values)(I(g)) == 5 and circuit.final(values, AC(sp.Integer(1)))(I(g)) == 5
