"""Circuits built of primitives, closed in any of the equivalent ways, and the problems set on them."""

import json
import math

import pytest
import sympy as sp
from electro import (
    AC,
    GND,
    Ammeter,
    Capacitor,
    ElementTwice,
    I,
    JoinsNodes,
    Node,
    NoSuchParameter,
    NotClosed,
    Parameter,
    Problem,
    Resistor,
    U,
    V,
    Voltage,
    VoltageSource,
    free,
    from_netlist,
    is_closed,
    simulate,
    solve,
    to_netlist,
    two_terminal,
)


def test_a_loop_closed_by_one_node_its_two_ends_on_it():
    e, r1, r2 = VoltageSource("E"), Resistor("R_1"), Resistor("R_2")
    a = Node()
    loop_ = a >> e >> r1 >> r2 >> a
    assert is_closed(loop_)
    s = solve(Problem(loop_, {e: 12, r1: 10, r2: 20}))
    assert s(I(r1)) == sp.Rational(2, 5) and s(U(r2)) == 8


def test_closing_by_a_node_by_ground_and_by_cup_and_cap_is_the_same():
    def current(build):
        e, r = VoltageSource("E"), Resistor("R")
        return solve(Problem(build(e, r), {e: 10, r: 5}))(I(r))

    a = Node()
    assert current(lambda e, r: a >> e >> r >> a) == 2
    assert current(lambda e, r: GND >> e >> r >> GND) == 2
    assert current(lambda e, r: ~(e >> r)) == 2


def test_parallel_by_shared_nodes_or_by_the_bar_is_the_same():
    def total(build):
        e, r1, r2 = VoltageSource("E"), Resistor("R_1"), Resistor("R_2")
        return solve(Problem(build(e, r1, r2), {e: 10, r1: 10, r2: 10}))(I(e))

    a, b = Node(), Node()
    assert total(lambda e, r1, r2: (a >> e >> b) @ (b >> r1 >> a) @ (b >> r2 >> a)) == 2
    assert total(lambda e, r1, r2: ~(e >> (r1 | r2))) == 2


def test_only_a_closed_circuit_is_a_problem_and_a_piece_says_how_many_ends_it_has_free():
    e, r = VoltageSource("E"), Resistor("R")
    assert free(e >> r) == (1, 1)
    with pytest.raises(NotClosed):
        Problem(e >> r, {e: 1, r: 1})


def test_series_never_glues_two_different_nodes_quietly():
    a, b = Node(), Node()
    with pytest.raises(JoinsNodes):
        (a >> VoltageSource("E1") >> Resistor("R1") >> a) >> (b >> VoltageSource("E2") >> Resistor("R2") >> b)


def test_two_nodes_labelled_alike_are_still_two():
    e, r1, r2 = VoltageSource("E"), Resistor("R_1"), Resistor("R_2")
    b1, b2 = Node("B"), Node("B")
    s = solve(Problem(GND >> e >> b1 >> r1 >> b2 >> r2 >> GND, {e: 12, r1: 10, r2: 20}))
    assert s(V(b1)) == 12 and s(V(b2)) == 8


def test_one_element_is_in_one_place():
    r = Resistor("R")
    with pytest.raises(ElementTwice):
        GND >> VoltageSource("E") >> r >> r >> GND


def test_elements_named_alike_share_a_value_each_its_own_current():
    e, ra, rb = VoltageSource("E"), Resistor("R"), Resistor("R")
    s = solve(Problem(GND >> e >> ra >> Node() >> rb >> GND, {"R": 50, e: 10}))
    assert s(I(ra)) == s(I(rb)) == sp.Rational(1, 10) and s(U(ra)) == 5
    with pytest.raises(NoSuchParameter):
        Problem(GND >> e >> ra >> GND, {"R_9": 1})


def test_an_inverse_problem_a_current_given_a_resistance_found():
    e, r1, r2 = VoltageSource("E"), Resistor("R_1"), Resistor("R_2")
    p = Problem(GND >> e >> r1 >> r2 >> GND, {e: 12, r1: 10, I(r1): "0.2"}, [Parameter(r2)])
    assert solve(p).answers == {Parameter(r2): 50}


def test_rc_on_paper_where_it_ends_in_time_how_it_gets_there_at_omega_its_phasor():
    e, r, c = VoltageSource("E"), Resistor("R"), Capacitor("C")
    b = Node("B")
    p = Problem((GND >> e >> r >> b) @ (b >> c >> GND), {e: 10, r: 1000, c: "100u"}, [U(c)])
    assert solve(p)(U(c)) == 10
    trace = simulate(p, until=0.5, dt=1e-4)
    assert abs(trace.at(U(c), 0.1) - 10 * (1 - math.exp(-1))) < 0.05
    phasor = solve(p, AC(sp.Integer(10)))(U(c))
    assert abs(complex(phasor)) == pytest.approx(10 / math.sqrt(2))


def test_a_new_element_is_one_law_and_nothing_else():
    Conductance = two_terminal("conductance", "G", lambda u, i, g: i - g * u)
    e, g = VoltageSource("E"), Conductance("G")
    p = Problem(GND >> e >> g >> GND, {e: 10, g: "0.5"})
    assert solve(p)(I(g)) == 5 and solve(p, AC(sp.Integer(1)))(I(g)) == 5


def test_written_down_and_read_back_it_solves_the_same():
    e, r1, r2 = VoltageSource("E"), Resistor("R_1"), Resistor("R_2")
    b = Node("B")
    p = Problem((GND >> e >> r1 >> b) @ (b >> r2 >> GND), {e: 12, r1: 10, r2: 20}, [I(r1), V(b)])
    data = json.loads(json.dumps(to_netlist(p)))
    again = from_netlist(data).problem
    assert list(solve(again).answers.values()) == list(solve(p).answers.values()) == [sp.Rational(2, 5), 8]


def test_a_meters_reading_is_written_down_as_its_value():
    e, r, a = VoltageSource("E"), Resistor("R"), Ammeter("A_1")
    data = to_netlist(Problem(~(e >> r >> a), {r: 3, I(a): 2}))
    assert [x.get("value") for x in data["elements"]] == [None, "3", "2"] and data["given"] == []
    again = from_netlist(data)
    assert solve(again.problem)(Voltage(again.elements["R"])) == 6
