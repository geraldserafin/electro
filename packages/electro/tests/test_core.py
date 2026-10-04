"""The prototype of the redesign (electro.core, DESIGN.md §9): what it promises, each as a test."""

import json
import math

import pytest
import sympy as sp
from electro.core import (
    AC,
    GND,
    Capacitor,
    ElementTwice,
    I,
    JoinsNodes,
    Kind,
    Node,
    NoSuchParameter,
    NotClosed,
    Parameter,
    Problem,
    Resistor,
    U,
    V,
    VoltageSource,
    close,
    free,
    is_closed,
    netlist,
    problem_from_data,
    problem_to_data,
    simulate,
    solve,
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
    assert current(lambda e, r: close(e >> r)) == 2


def test_parallel_by_shared_nodes_or_by_the_bar_is_the_same():
    def total(build):
        e, r1, r2 = VoltageSource("E"), Resistor("R_1"), Resistor("R_2")
        return solve(Problem(build(e, r1, r2), {e: 10, r1: 10, r2: 10}))(I(e))

    a, b = Node(), Node()
    assert total(lambda e, r1, r2: (a >> e >> b) @ (b >> r1 >> a) @ (b >> r2 >> a)) == 2
    assert total(lambda e, r1, r2: close(e >> (r1 | r2))) == 2


def test_only_a_closed_circuit_is_a_problem_and_a_piece_says_how_many_ends_it_has_free():
    e, r = VoltageSource("E"), Resistor("R")
    assert free(e >> r) == (1, 1)
    with pytest.raises(NotClosed):
        Problem(e >> r, {e: 1, r: 1})


def test_series_never_glues_two_different_nodes_quietly():
    # two closed loops chained: their nodes would merge into one — said, not done
    a, b = Node(), Node()
    with pytest.raises(JoinsNodes):
        (a >> VoltageSource("E1") >> Resistor("R1") >> a) >> (b >> VoltageSource("E2") >> Resistor("R2") >> b)


def test_two_nodes_labelled_alike_are_still_two():
    e, r1, r2 = VoltageSource("E"), Resistor("R_1"), Resistor("R_2")
    b1, b2 = Node("B"), Node("B")  # (a label only shows)
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
    assert solve(p)(U(c)) == 10  # a capacitor in DC: open, read from its law (D → 0)
    trace = simulate(p, until=0.5, dt=1e-4)
    assert abs(trace(U(c))(0.1) - 10 * (1 - math.exp(-1))) < 0.05  # τ = RC = 0.1 s
    phasor = solve(p, AC(sp.Integer(10)))(U(c))  # ω = 1/RC: |U_C| = E/√2
    assert abs(complex(phasor)) == pytest.approx(10 / math.sqrt(2))


def test_a_new_element_is_one_law_and_nothing_else():
    # a conductance, unknown to everything else: given by its law alone, it works in every analysis
    Conductance = Kind("conductance", "G", "S", lambda u, i, g: i - g * u)
    e, g = VoltageSource("E"), Conductance("G")
    p = Problem(GND >> e >> g >> GND, {e: 10, g: "0.5"})
    assert solve(p)(I(g)) == 5 and solve(p, AC(sp.Integer(1)))(I(g)) == 5


def test_written_down_and_read_back_it_solves_the_same():
    e, r1, r2 = VoltageSource("E"), Resistor("R_1"), Resistor("R_2")
    b = Node("B")
    p = Problem((GND >> e >> r1 >> b) @ (b >> r2 >> GND), {e: 12, r1: 10, r2: 20}, [I(r1), V(b)])
    data = json.loads(json.dumps(problem_to_data(p)))
    again, _ = problem_from_data(data)
    assert list(solve(again).answers.values()) == list(solve(p).answers.values()) == [sp.Rational(2, 5), 8]


# --- the engine's operations and the methods over them (DESIGN.md §12) ----------------------------


def test_a_pieces_black_box_matched_to_a_kind_finds_the_rules_nobody_wrote():
    from electro.core.problem import blackbox, matches
    from electro.core.syntax import CurrentSource

    r1, r2 = Resistor("R_1"), Resistor("R_2")
    R1, R2, E1, E2 = sp.symbols("R_1 R_2 E_1 E_2")
    assert matches(blackbox(r1 >> r2), Resistor) == R1 + R2  # series
    assert sp.simplify(matches(blackbox(r1 | r2), Resistor) - R1 * R2 / (R1 + R2)) == 0  # parallel
    assert matches(blackbox(VoltageSource("E_1") >> VoltageSource("E_2")), VoltageSource) == E1 + E2
    # a resistor is no source, and a source with a resistor is no single element (that takes two)
    assert matches(blackbox(r1 >> r2), VoltageSource) is None
    one = blackbox(VoltageSource("E") >> Resistor("R"))
    assert all(matches(one, k) is None for k in (Resistor, VoltageSource, CurrentSource))
    # in AC a resistor and a capacitor are an impedance: R + 1/(jωC), from the capacitor's law alone
    w, R, C = sp.symbols("w R C")
    z = matches(blackbox(Resistor("R") >> Capacitor("C"), AC(w)), Resistor, AC(w))
    assert sp.simplify(z - (R + 1 / (sp.I * w * C))) == 0


def test_simplifying_step_by_step_as_a_book_does_its_equivalent_circuits():
    from electro.core.methods import simplify

    e, r1, r2, r3, r4 = VoltageSource("E"), Resistor("R_1"), Resistor("R_2"), Resistor("R_3"), Resistor("R_4")
    a, b = Node("A"), Node("B")
    circuit = (GND >> e >> r1 >> a) @ (a >> r2 >> GND) @ (a >> r3 >> b) @ (b >> r4 >> GND)
    p = Problem(circuit, {e: 12, r1: 2, r2: 6, r3: 1, r4: 2}, [I(e)])
    simpler, steps = simplify(p)
    assert [(s.how, s.by.name, s.amount) for s in steps] == [
        ("series", "R_34", 3),
        ("parallel", "R_234", 2),
        ("series", "R_1234", 4),
    ]
    assert len(netlist(simpler.circuit).parts) == 2  # E and one resistor
    assert solve(simpler)(I(e)) == solve(p)(I(e)) == 3  # the same where it is asked about


def test_superposition_each_source_alone_then_summed_and_never_for_a_diode():
    from electro.core.methods import NotLinear, superposition
    from electro.core.syntax import CurrentSource

    e, j, r1, r2 = VoltageSource("E"), CurrentSource("J"), Resistor("R_1"), Resistor("R_2")
    a = Node("A")
    circuit = (GND >> e >> r1 >> a) @ (a >> r2 >> GND) @ (GND >> j >> a)
    p = Problem(circuit, {e: 12, j: 2, r1: 4, r2: 4})
    s = superposition(p, I(r2))
    assert dict(s.parts) == {e: sp.Rational(3, 2), j: 1} and s.total == solve(p)(I(r2))
    diode = Kind("diode", "D", "", lambda u, i, i_s: i - i_s * (sp.exp(u) - 1), symmetric=False)
    with pytest.raises(NotLinear):
        superposition(Problem(GND >> e >> diode("D") >> GND, {e: 1, "D": "1e-12"}), I(e))
