"""The engine's operations and the textbook methods over them (DESIGN.md §12)."""

import pytest
import sympy as sp
from electro.core import (
    AC,
    GND,
    Capacitor,
    CurrentSource,
    I,
    Node,
    NotLinear,
    Problem,
    Resistor,
    VoltageSource,
    blackbox,
    matches,
    netlist,
    simplify,
    solve,
    superposition,
    two_terminal,
)


def test_a_pieces_black_box_matched_to_a_kind_finds_the_rules_nobody_wrote():
    r1, r2 = Resistor("R_1"), Resistor("R_2")
    R1, R2, E1, E2 = sp.symbols("R_1 R_2 E_1 E_2")
    assert matches(blackbox(r1 >> r2), Resistor) == R1 + R2
    assert sp.simplify(matches(blackbox(r1 | r2), Resistor) - R1 * R2 / (R1 + R2)) == 0
    assert matches(blackbox(VoltageSource("E_1") >> VoltageSource("E_2")), VoltageSource) == E1 + E2
    assert matches(blackbox(r1 >> r2), VoltageSource) is None
    one = blackbox(VoltageSource("E") >> Resistor("R"))
    assert all(matches(one, k) is None for k in (Resistor, VoltageSource, CurrentSource))
    w, R, C = sp.symbols("w R C")
    z = matches(blackbox(Resistor("R") >> Capacitor("C"), AC(w)), Resistor, AC(w))
    assert sp.simplify(z - (R + 1 / (sp.I * w * C))) == 0


def test_simplifying_step_by_step_as_a_book_does_its_equivalent_circuits():
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
    assert len(netlist(simpler.circuit).parts) == 2
    assert solve(simpler)(I(e)) == solve(p)(I(e)) == 3


def test_superposition_each_source_alone_then_summed_and_never_for_a_diode():
    e, j, r1, r2 = VoltageSource("E"), CurrentSource("J"), Resistor("R_1"), Resistor("R_2")
    a = Node("A")
    circuit = (GND >> e >> r1 >> a) @ (a >> r2 >> GND) @ (GND >> j >> a)
    p = Problem(circuit, {e: 12, j: 2, r1: 4, r2: 4})
    s = superposition(p, I(r2))
    assert dict(s.parts) == {e: sp.Rational(3, 2), j: 1} and s.total == solve(p)(I(r2))
    diode = two_terminal("diode", "D", lambda u, i, i_s: i - i_s * (sp.exp(u) - 1))
    with pytest.raises(NotLinear):
        superposition(Problem(GND >> e >> diode("D") >> GND, {e: 1, "D": "1e-12"}), I(e))
