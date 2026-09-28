"""Typical school problems."""

import pytest
import sympy as sp

import electro

from electro import *
from electro.issues import ConflictingData, Equals, ParallelMismatch, SeriesMismatch
from electro.reasons import OhmsLaw


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


def test_type_errors_say_which():
    with pytest.raises(SeriesMismatch) as err:
        Resistor(1) + split + Resistor(1)
    assert (err.value.outputs, err.value.inputs) == (2, 1)
    with pytest.raises(ParallelMismatch):
        Resistor(1) | split
    with pytest.raises(TypeError):  # still the built-in error they stand for
        Resistor(1) | split


def _step(sol, name):
    return next(s for s in sol.shown_steps() if name in {t.name for t in s.targets})


def test_steps_keep_their_laws():
    sol = (supply(12) + Resistor(10) + Resistor() + ground).solve(I_R1=0.5)
    step = _step(sol, "R_2")
    assert step.laws[0].reason == OhmsLaw(sp.Symbol("R_2"))
    assert str(step.formula) == "U_R_2/I_R_2" and list(step.targets.values()) == [14]


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


def test_find_prunes_the_trace():
    sol = _three_unknowns().solve(I_R_1=2, U_R_2=8, find="R_1")
    assert str(_step(sol, "R_1").formula) == "U_R_1/I_R_1"
    assert "I_J_1" not in {t.name for s in sol.shown_steps() for t in s.targets}  # not needed for R_1


def test_missing_data_says_what_would_help():
    with pytest.raises(MissingData) as err:
        _three_unknowns().solve(I_R_1=2, U_R_2=8, find=["R_1", "R_3", "E_2"])
    assert [t.name for t in err.value.targets] == ["R_3", "E_2"] and err.value.needed == 1
    assert any(s.name == "U_R_3" for option in err.value.options for s in option)
    assert err.value.solution.answers["R_1"] == 2  # the part that could be found is kept


def test_missing_data_counts_redundant_givens_once():
    with pytest.raises(MissingData) as err:
        _three_unknowns().solve(U_R_2=8, I_R_2=2, find=["R_1", "R_3", "E_2"])
    assert err.value.needed == 2


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
    assert isinstance(err.value, ConflictingData)
    shown = lambda data: {(d.symbol.name, d.value, d.unit) for d in data if isinstance(d, Equals)}
    assert shown(err.value.conditions) == {("I_R_1", 5, "A")} and ("E_1", 12, "V") in shown(err.value.values)


def test_hole_with_no_current_is_a_break():
    c = loop(VoltageSource(12), Resistor(10), Hole())
    sol = c.solve(I_R_1=0)
    assert sol.realize("X_1") is electro.components.OPEN
    assert sol["X_1"].U == 12  # all of the voltage sits across the break


def test_two_solutions_are_named():
    with pytest.raises(Ambiguous) as err:
        loop(VoltageSource(12), Resistor(), Resistor(4)).solve(P_R_1=8)
    assert [[(d.symbol.name, d.value) for d in option] for option in err.value.options] == [[("R_1", 8)], [("R_1", 2)]]
    sol = loop(VoltageSource(12), Resistor(), Resistor(4)).solve(Eq(P("R_1"), 8), Eq(U("R_1"), 2 * U("R_2")))
    assert sol["R_1"].value == 8  # one more condition picks one


def test_ammeter_reading_is_a_datum():
    """Zadanie 4: I_2 = 2 A measured → the supply voltage; the load's equivalent resistance."""
    load = Resistor(3) + ((Resistor(18) + Ammeter(2)) | (Resistor(3) + Resistor(6)))
    assert loop(VoltageSource(label="E"), load).solve(find="E")["E"].value == 54
    assert electro.resistance(load) == 9


def test_meter_without_reading_reads_the_result():
    sol = loop(VoltageSource(12), Resistor(4), Ammeter(), Voltmeter() | Resistor(2)).solve()
    assert sol["A_1"].value == 2 and sol["V_1"].value == 4


def test_meter_reading_can_contradict():
    with pytest.raises(Contradiction) as err:
        loop(VoltageSource(12), Resistor(4), Ammeter(2)).solve()
    assert ("A_1", 2) in {(d.symbol.name, d.value) for d in err.value.values}
