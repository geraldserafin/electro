"""Typical school problems."""

import pytest
import sympy as sp

from electro import *


def test_divider_with_unknown_resistor():
    c = supply(12) + Resistor(10) + Resistor() + ground
    sol = c.solve(I_R1=0.5)
    assert sol["R2"].value == 14
    assert sol["R2"].U == 7
    assert sol["E1"].P == 6


def test_givens_in_many_forms():
    c = supply(12) + Resistor(10) + Resistor() + ground
    for sol in (c.solve({I("R1"): "500m"}), c.solve(Eq(U("R1"), 5)), c.solve(I_R1="0,5 A")):
        assert sol["R2"].value == 14


def test_series_parallel_resistance():
    assert resistance(Resistor(10) + (Resistor(20) | Resistor(30))) == 22
    assert resistance(parallel(Resistor(6), Resistor(3), Resistor(2))) == 1
    assert resistance(Resistor("4k7") + Resistor("300")) == 5000


def test_loop():
    sol = loop(VoltageSource(12), Resistor(4), Resistor(2)).solve()
    assert sol["R1"].I == 2
    assert sol["R2"].U == 4


def test_parallel_branch_currents():
    sol = (supply(12) + (Resistor(6) | Resistor(3)) + ground).solve()
    assert (sol["R1"].I, sol["R2"].I, sol["E1"].I) == (2, 4, 6)


def test_shunt_and_named_node():
    c = supply(10) + Resistor(1000) + node("out") + shunt(Resistor(4000))
    sol = c.solve()
    assert sol.V("out") == 8


def test_thevenin_of_divider():
    th = equivalent(supply(12) + Resistor(10) + shunt(Resistor(10)))
    assert (th.E, th.Z) == (6, 5)


def test_symbolic_answer():
    sol = (supply("E") + Resistor("R") + Resistor("R") + ground).solve()
    assert sp.simplify(sol["R2"].U - sp.Symbol("E") / 2) == 0


def test_wheatstone_bridge_balanced():
    c = net(
        (VoltageSource(10), "0", "A"),
        (Resistor(100), "A", "B"), (Resistor(200), "B", "0"),
        (Resistor(50), "A", "C"), (Resistor(100), "C", "0"),
        (Ammeter(), "B", "C"),
    )
    assert c.solve()["A1"].I == 0


def test_wheatstone_bridge_unknown_resistor():
    c = net(
        (VoltageSource(10), "0", "A"),
        (Resistor(100), "A", "B"), (Resistor(), "B", "0"),
        (Resistor(50), "A", "C"), (Resistor(100), "C", "0"),
        (Ammeter(), "B", "C"),
    )
    assert c.solve(I_A1=0)["R2"].value == 200


def test_inverting_amplifier():
    c = net(
        (VoltageSource(1), "0", "in"),
        (Resistor("1k"), "in", "x"),
        (Resistor("10k"), "x", "out"),
        (OpAmp(), "0", "x", "out"),
    )
    assert c.solve().V("out") == -10


def test_ac_impedance():
    assert resistance(Resistor(1) + Capacitor(1), omega=1) == 1 - sp.I
    assert resistance(Resistor(1) + Inductor(1), omega=2) == 1 + 2 * sp.I


def test_dc_capacitor_blocks():
    sol = (supply(5) + Resistor(100) + Capacitor("1u") + ground).solve()
    assert sol["R1"].I == 0 and sol["C1"].U == 5


def test_contradiction():
    with pytest.raises(Contradiction):
        loop(VoltageSource(12), Resistor(10)).solve(I_R1=5)


def test_underdetermined_warns():
    with pytest.warns(UserWarning, match="R_2"):
        sol = (supply(12) + Resistor(10) + Resistor() + ground).solve()
    assert sol["R2"].value is None


def test_two_solutions_from_power():
    with pytest.raises(Ambiguous):
        loop(VoltageSource(12), Resistor(), Resistor(4)).solve(P_R1=8)


def test_type_errors_are_readable():
    with pytest.raises(TypeError, match="szeregowo"):
        Resistor(1) + split + Resistor(1)
    with pytest.raises(TypeError, match="równoległe"):
        Resistor(1) | split


def test_explain_mentions_laws():
    text = (supply(12) + Resistor(10) + Resistor() + ground).solve(I_R1=0.5).explain()
    assert "prawo Ohma (R_2)" in text and "R_2 = U_R_2/I_R_2 = 7/0.5 = 14 Ω" in text


def test_three_sources_as_parallel_branches():
    """Whiteboard: E1+R1 | R2 | E2+(R3|Iz) between the top node and ground."""
    uklad = (VoltageSource(12) + Resistor(2)) | Resistor(4) | ((Resistor(6) | CurrentSource(1)) + VoltageSource(6).transpose())
    sol = uklad.solve()
    assert sol["R2"].I == sp.Rational(-18, 11)  # branch read bottom → top; the board draws it downward
    parts = [
        ((VoltageSource(e1) + Resistor(2)) | Resistor(4) | ((Resistor(6) | CurrentSource(iz)) + VoltageSource(e2).transpose())).solve()["R2"].I
        for e1, e2, iz in [(12, 0, 0), (0, 6, 0), (0, 0, 1)]
    ]
    assert sum(parts) == sol["R2"].I  # superposition


def test_auto_labels_use_subscripts_and_skip_taken_ones():
    sol = (supply(12) + Resistor(1) + Resistor(2, label="R2") + Resistor(3) + ground).solve()
    assert list(sol.system.parts) == ["E_1", "R_1", "R2", "R_3"]
    assert sol["R1"].value == 1  # underscores are optional when looking things up


def test_unknown_resistor_in_three_source_circuit():
    uklad = (
        (VoltageSource(12) + Resistor(2))
        | Resistor(4).transpose()
        | ((Resistor().transpose() | CurrentSource(1)) + VoltageSource(6).transpose())
    )
    sol = uklad.solve(I_R_2=sp.Rational(18, 11))
    assert sol["R_3"].value == 6


def _three_unknowns():
    return (
        (VoltageSource(12) + Resistor())
        | Resistor(4).transpose()
        | ((Resistor().transpose() | CurrentSource(1)) + VoltageSource().transpose())
    )


def test_find_several_unknowns():
    sol = _three_unknowns().solve(I_R_1=2, U_R_2=8, U_R_3=5, find=["R_1", "R_3", "E_2"])
    assert sol.answers == {"R_1": 2, "R_3": 5, "E_2": -3}
    assert "Odpowiedź:" in sol.explain()


def test_find_prunes_the_trace():
    text = _three_unknowns().solve(I_R_1=2, U_R_2=8, find="R_1").explain()
    assert "R_1 = U_R_1/I_R_1 = 4/2 = 2 Ω" in text
    assert "I_J_1" not in text  # not needed for R_1


def test_missing_data_says_what_would_help():
    with pytest.raises(MissingData) as err:
        _three_unknowns().solve(I_R_1=2, U_R_2=8, find=["R_1", "R_3", "E_2"])
    message = str(err.value)
    assert "R_3, E_2" in message and "brakuje 1 danej" in message and "U_R_3" in message
    assert err.value.solution.answers["R_1"] == 2  # the part that could be found is kept


def test_missing_data_counts_redundant_givens_once():
    with pytest.raises(MissingData, match="brakuje 2 danych"):
        _three_unknowns().solve(U_R_2=8, I_R_2=2, find=["R_1", "R_3", "E_2"])


def test_hole_becomes_the_simplest_element():
    c = supply(12) + Resistor(10) + Hole() + ground
    sol = c.solve(I_R_1=0.5)
    assert repr(sol.realize("X_1")) == "Resistor(14 Ω)"
    assert sol.assumed  # "E = 0" was assumed, and the trace says so
    filled = c.fill(sol)
    assert filled.solve()["R_1"].I == sp.Rational(1, 2)  # the filled circuit reproduces the data


def test_hole_needs_a_source_when_current_flows_backwards():
    c = supply(12) + Resistor(10) + Hole() + ground
    assert repr(c.solve(I_R_1=-0.5).realize("X_1")) == "VoltageSource(17 V).transpose()"


def test_hole_can_be_a_plain_wire():
    c = supply(12) + Resistor(10) + Hole() + ground
    assert repr(c.fill(c.solve(I_R_1="1,2"))) == "ground.transpose() + VoltageSource(12 V) + Resistor(10 Ω) + wire + ground"


def test_unknown_resistor_cannot_be_negative():
    with pytest.raises(Contradiction):
        (supply(12) + Resistor(10) + Resistor() + ground).solve(I_R_1=-0.5)


def test_unknown_source_can_come_out_positive():
    sol = loop(VoltageSource(), Resistor(10)).solve(I_R_1=5)
    assert sol["E_1"].value == 50


def test_contradiction_names_the_clashing_data():
    with pytest.raises(Contradiction) as err:
        loop(VoltageSource(12), Resistor(10)).solve(I_R_1=5)
    message = str(err.value)
    assert message.startswith("Sprzeczne dane:") and "E_1 = 12 V" in message and "I_R_1 = 5 A" in message
    assert "\n" not in message  # one line, not a dump of the equations
