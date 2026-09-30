"""Typical school problems."""

import electro
import pytest
import sympy as sp
from electro import *
from electro.issues import ConflictingData, Equals, ParallelMismatch, SeriesMismatch
from electro.reasons import ControlledSource, OhmsLaw
from electro.values import parse


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
        (Resistor(100), "A", "B"),
        (Resistor(200), "B", "0"),
        (Resistor(50), "A", "C"),
        (Resistor(100), "C", "0"),
        (Ammeter(), "B", "C"),
    )
    assert c.solve()["A1"].I == 0


def test_wheatstone_bridge_unknown_resistor():
    c = net(
        (VoltageSource(10), "0", "A"),
        (Resistor(100), "A", "B"),
        (Resistor(), "B", "0"),
        (Resistor(50), "A", "C"),
        (Resistor(100), "C", "0"),
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


def test_ac_power_is_average():
    sol = (supply(1) + Resistor(1000) + Capacitor(1e-6) + ground).solve(omega=1000)
    assert float(sol["R1"].P) == pytest.approx(0.25e-3)  # ½·|I|²·R, |I| = 1/√2 mA
    assert sol["C1"].P == 0


def test_bode_rc_low_pass():
    r = bode(supply(12) + Resistor("1k") + node("A") + Capacitor("1u") + ground, "V_A")
    at = lambda f: min(range(len(r.f)), key=lambda k: abs(r.f[k] - f))  # noqa: E731
    fc = at(1 / (2 * 3.14159265 * 1e-3))
    gain, phase = r.gain_db["V_A"], r.phase_deg["V_A"]
    assert r.input == "E_1" and gain[0] == pytest.approx(0, abs=0.05)
    assert gain[fc] == pytest.approx(-3, abs=0.1) and phase[fc] == pytest.approx(-45, abs=1)
    assert gain[at(1e5)] - gain[at(1e4)] == pytest.approx(-20, abs=0.5)  # −20 dB a decade
    assert "<polyline" in r._repr_svg_()
    [corner] = r.cutoffs()
    assert corner == pytest.approx(1 / (2 * 3.14159265 * 1e-3), rel=0.01) and "160Hz" in r._repr_svg_()


def test_bode_outputs_by_default():
    named = supply(1) + Resistor(10) + node("A") + Inductor("1m") + node("B") + Capacitor("1u") + ground
    assert list(bode(named).H) == ["V_A", "V_B"]
    assert list(bode(supply(1) + node("IN") + Resistor(10) + node("OUT") + Capacitor("1u") + ground).H) == ["V_OUT"]
    assert list(bode(supply(1) + Resistor(10) + Inductor("1m") + Capacitor("1u") + ground).H) == ["U_L_1", "U_C_1"]


def test_sweep_a_divider():
    s = sweep(supply(12) + Resistor("1k") + node("A") + Resistor() + ground, "R2", ("100", "10k"), points=3)
    assert s.t == [100, 5050, 10000] and s["V_A"][0] == pytest.approx(12 * 100 / 1100)
    assert "R<tspan" in s._repr_svg_()  # the x axis is the resistance


def test_sweep_at_a_frequency_gives_amplitudes():
    s = sweep(supply(1) + Resistor("1k") + Capacitor("1u") + ground, "C1", ["1u", "1n"], omega=1000)
    assert s["U_C_1"] == pytest.approx([1 / abs(1 + 1j), 1 / abs(1 + 1e-3j)])


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
    uklad = (
        (VoltageSource(12) + Resistor(2))
        | Resistor(4)
        | ((Resistor(6) | CurrentSource(1)) + VoltageSource(6).transpose())
    )
    sol = uklad.solve()
    assert sol["R2"].I == sp.Rational(-18, 11)  # branch read bottom → top; the board draws it downward
    parts = [
        (
            (VoltageSource(e1) + Resistor(2))
            | Resistor(4)
            | ((Resistor(6) | CurrentSource(iz)) + VoltageSource(e2).transpose())
        )
        .solve()["R2"]
        .I
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
    assert (
        repr(c.fill(c.solve(I_R_1="1,2")))
        == "ground.transpose() + VoltageSource(12 V) + Resistor(10 Ω) + wire + ground"
    )


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


# ------------------------------------------------------------------ controlled sources


def test_vcvs_amplifies_the_voltage_it_senses():
    amp = net(
        (VoltageSource(2), "GND", "in"),
        (Resistor(1000), "in", "GND"),
        (VCVS(10), "in", "GND", "GND", "out"),
        (Resistor(50), "out", "GND"),
    )
    sol = amp.solve()
    assert sol["VCVS_1"].U == 20
    assert sol["R_2"].I == sp.Rational(2, 5)
    assert sol["E_1"].I == sp.Rational(2, 1000)  # the control side draws nothing


def test_vccs_is_a_transconductance():
    sol = net(
        (VoltageSource(2), "GND", "in"), (VCCS("0.5"), "in", "GND", "GND", "out"), (Resistor(10), "out", "GND")
    ).solve()
    assert sol["R_1"].U == 10


def test_ccvs_and_cccs_sense_the_current_in_series():
    loop_ = [(VoltageSource(10), "GND", "a"), (Resistor(5), "a", "b")]  # 2 A through the sensing branch b → GND
    ccvs = net(*loop_, (CCVS(3), "b", "GND", "GND", "out"), (Resistor(1), "out", "GND")).solve()
    assert ccvs["R_2"].U == 6 and ccvs["CCVS_1"].I == 6
    cccs = net(*loop_, (CCCS(10), "b", "GND", "GND", "out"), (Resistor(1), "out", "GND")).solve()
    assert cccs["R_2"].I == 20
    assert cccs["E_1"].I == 2  # the sensing branch drops nothing: the loop keeps its 2 A


def test_the_gain_is_found_from_the_data():
    # a transistor stage as its small-signal model: r_be, then β·I_b into the collector's resistor
    stage = net(
        (VoltageSource("10m"), "GND", "in"),
        (Resistor(1000), "in", "b"),
        (CCCS(), "b", "GND", "GND", "c"),
        (Resistor(2000), "c", "GND"),
    )
    sol = stage.solve(U_R_2=2, find="CCCS_1")
    assert sol["CCCS_1"].value == 100
    assert any(isinstance(law.reason, ControlledSource) for step in sol.steps for law in step.laws)


def test_controlled_sources_simulate_and_come_back_as_code():
    amp = net((VoltageSource(2), "GND", "in"), (VCVS(-3), "in", "GND", "GND", "out"), (Resistor(50), "out", "GND"))
    assert simulate(amp, t=1e-3).at(1e-3)["V_out"] == pytest.approx(-6)
    scope: dict = {}
    exec("from electro import *\n" + code(amp), scope)
    assert scope["uklad"].solve()["R_1"].U == -6


def test_ideal_transformer_steps_down():
    """n = 2: half the voltage, twice the current, the same power."""
    c = net((VoltageSource(10), "GND", "A"), (Transformer(2), "A", "GND", "GND", "B"), (Resistor(10), "B", "GND"))
    sol = c.solve(omega=100)
    assert sol["R1"].U == 5 and sol["R1"].I == sp.Rational(1, 2)
    assert sol(sp.Symbol("I1_TR_1")) == sp.Rational(1, 4) and sol(sp.Symbol("U2_TR_1")) == 5
    dc = net((VoltageSource(10), "GND", "S"), (Resistor(5), "S", "A"), (Transformer(2), "A", "GND", "GND", "B"))
    assert dc.solve()["R1"].I == 2  # DC: the primary is a short circuit


def test_coupled_inductors():
    """Secondary open: U₂ = jωM·I₁, and I₁ sees only jωL₁."""
    c = net(
        (VoltageSource(1), "GND", "A"),
        (Resistor(1), "A", "B"),
        (Coupled("1m", L1="2m", L2="3m"), "B", "GND", "GND", "C"),
        (Resistor("1G"), "C", "GND"),
    )
    sol = c.solve(omega=1000)
    i1 = complex(sol(sp.Symbol("I1_M_1")))
    assert i1 == pytest.approx(1 / (1 + 2j), rel=1e-6)
    assert complex(sol(sp.Symbol("U2_M_1"))) == pytest.approx(1j * i1, rel=1e-6)


def test_three_phase_star_and_delta():
    balanced = three_phase(230) | star(Resistor(10))
    sol = balanced.solve(omega=314)
    neutral = sum(sol(sp.Symbol(f"I_E_{k}")) for k in (1, 2, 3))
    assert sp.simplify(neutral) == 0  # balanced: nothing in the neutral
    # unbalanced, three wires: the star point floats away from the source's neutral
    floating = (three_phase(230) | star(Resistor(10), Resistor(20), Resistor(30), neutral="N0")).solve(omega=314)
    assert abs(complex(floating.V("N0"))) > 1
    # delta: each load between two lines, at √3 the phase voltage and 30° ahead
    d = (three_phase(230) | delta(Resistor(10))).solve(omega=314)
    assert (d["R1"].U - 230 * sp.sqrt(3) * sp.exp(sp.I * sp.pi / 6)).expand(complex=True) == 0


def test_phasor_strings():
    assert parse("230∠-120") == -115 - 115 * sp.sqrt(3) * sp.I
    assert parse("3+4j") == 3 + 4 * sp.I
    assert VoltageSource("10∠90").value == 10 * sp.I


def test_tolerance_of_a_divider():
    """Two 5 % resistors: the middle within ±5 % of half, most builds near it; the same seed, the same."""
    c = supply(12) + Resistor("10k") + node("A") + Resistor("10k") + ground
    spread = tolerance(c, tol=0.05, runs=400)
    s = spread.stats("V_A")
    assert s["mean"] == pytest.approx(6, abs=0.03) and 5.7 <= s["min"] and s["max"] <= 6.3
    assert tolerance(c, tol=0.05, runs=400).values == spread.values
    assert tolerance(c, tol={"C": 0.1}, runs=5).stats("V_A")["std"] == 0  # no resistor varies
    assert "<rect" in spread._repr_svg_()
