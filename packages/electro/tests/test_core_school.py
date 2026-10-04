"""The library's school problems (test_school.py), each again on the prototype (electro.core), with the
same numbers — side by side: what it does as well, and (xfail, with why) what it does not do yet."""

import pytest
import sympy as sp
from electro.core import (
    AC,
    GND,
    VCVS,
    Capacitor,
    CurrentSource,
    I,
    Node,
    Parameter,
    Problem,
    Resistor,
    U,
    Undetermined,
    V,
    VoltageSource,
    at,
    blackbox,
    close,
    loop,
    solve,
)
from electro.core.methods import between, resistance, superposition, thevenin
from electro.core.problem import P
from electro.core.syntax import CCCS, CCVS, VCCS, Ammeter, OpAmp
from electro.core.syntax import Capacitor as C
from electro.values import parse

GAP = pytest.mark.xfail(strict=True)


def test_divider_with_unknown_resistor():
    e, r1, r2 = VoltageSource("E"), Resistor("R_1"), Resistor("R_2")
    s = solve(Problem(GND >> e >> r1 >> Node() >> r2 >> GND, {e: 12, r1: 10, I(r1): "0.5"}))
    assert (s(Parameter(r2)), s(U(r2)), -s(P(e))) == (14, 7, 6)  # (a source's power: minus what it gives)


def test_givens_in_many_forms():
    for given in ("500m", "0,5 A"):
        e, r1, r2 = VoltageSource("E"), Resistor("R_1"), Resistor("R_2")
        assert solve(Problem(GND >> e >> r1 >> Node() >> r2 >> GND, {e: 12, r1: 10, I(r1): given}))(Parameter(r2)) == 14
    e, r1, r2 = VoltageSource("E"), Resistor("R_1"), Resistor("R_2")
    assert solve(Problem(GND >> e >> r1 >> Node() >> r2 >> GND, {e: 12, r1: 10, U(r1): 5}))(Parameter(r2)) == 14


def test_series_parallel_resistance():
    # (rules found by black boxes — series, parallel — none written)
    assert (
        resistance(blackbox(Resistor("a") >> (Resistor("b") | Resistor("c")))).subs({"a": 10, "b": 20, "c": 30}) == 22
    )
    r = resistance(blackbox(Resistor("a") | Resistor("b") | Resistor("c")))
    assert r.subs({"a": 6, "b": 3, "c": 2}) == 1
    assert parse("4k7") + parse("300") == 5000


def test_loop():
    e, r1, r2 = VoltageSource("E"), Resistor("R_1"), Resistor("R_2")
    s = solve(Problem(loop(e, r1, r2), {e: 12, r1: 4, r2: 2}))
    assert (s(I(r1)), s(U(r2))) == (2, 4)


def test_parallel_branch_currents():
    e, r1, r2 = VoltageSource("E"), Resistor("R_1"), Resistor("R_2")
    a = Node()
    s = solve(Problem((GND >> e >> a) @ (a >> r1 >> GND) @ (a >> r2 >> GND), {e: 12, r1: 6, r2: 3}))
    assert (s(I(r1)), s(I(r2)), s(I(e))) == (2, 4, 6)


def test_shunt_and_named_node():
    e, r1, r2 = VoltageSource("E"), Resistor("R_1"), Resistor("R_2")
    out = Node("out")
    s = solve(Problem((GND >> e >> r1 >> out) @ (out >> r2 >> GND), {e: 10, r1: 1000, r2: 4000}))
    assert s(V(out)) == 8


def test_thevenin_of_divider():
    e, r1, r2 = VoltageSource("E"), Resistor("R_1"), Resistor("R_2")
    out = Node("out")
    p = Problem((GND >> e >> r1 >> out) @ (out >> r2 >> GND), {e: 12, r1: 10, r2: 10})
    th = thevenin(between(p, out, GND))
    assert th is not None and (th.E, th.Z) == (6, 5)


def test_symbolic_answer():
    e, r1, r2 = VoltageSource("E"), Resistor("R_1"), Resistor("R_2")
    s = solve(Problem(GND >> e >> r1 >> Node() >> r2 >> GND, {e: "E", r1: "R", r2: "R"}))
    assert sp.simplify(s(U(r2)) - sp.Symbol("E") / 2) == 0


def _bridge(r2_value):
    e, r1, r2, r3, r4, a1 = (
        VoltageSource("E"),
        Resistor("R_1"),
        Resistor("R_2"),
        Resistor("R_3"),
        Resistor("R_4"),
        Ammeter(),
    )
    a, b, c = Node("A"), Node("B"), Node("C")
    circuit = (GND >> e >> a) @ (a >> r1 >> b) @ (b >> r2 >> GND) @ (a >> r3 >> c) @ (c >> r4 >> GND) @ (b >> a1 >> c)
    given = {e: 10, r1: 100, r3: 50, r4: 100} | ({r2: r2_value} if r2_value is not None else {I(a1): 0})
    return Problem(circuit, given), r2, a1


def test_wheatstone_bridge_balanced():
    p, _, a1 = _bridge(200)
    assert solve(p)(I(a1)) == 0


def test_wheatstone_bridge_unknown_resistor():
    p, r2, _ = _bridge(None)
    assert solve(p)(Parameter(r2)) == 200


def test_inverting_amplifier():
    e, r1, r2, amp = VoltageSource("E"), Resistor("R_1"), Resistor("R_2"), OpAmp()
    x, out = Node("x"), Node("out")
    circuit = (GND >> e >> Node() >> r1 >> x) @ (x >> r2 >> out) @ at(amp, GND, x, out, GND)
    assert solve(Problem(circuit, {e: 1, r1: 1000, r2: 10000}))(V(out)) == -10


def test_ac_impedance():
    assert (
        resistance(blackbox(Resistor("R") >> C("C"), AC(sp.Integer(1))), AC(sp.Integer(1))).subs({"R": 1, "C": 1})
        == 1 - sp.I
    )
    from electro.core import Inductor

    assert (
        resistance(blackbox(Resistor("R") >> Inductor("L"), AC(sp.Integer(2))), AC(sp.Integer(2))).subs(
            {"R": 1, "L": 1}
        )
        == 1 + 2 * sp.I
    )


@GAP
def test_ac_power_is_average():
    raise NotImplementedError("power in AC: ½·Re(U·I*) — phasors need the conjugate, not U·I")


@GAP
def test_bode_rc_low_pass():
    raise NotImplementedError("bode, sweep, tolerance: the analyses over a range are not in the prototype")


def test_dc_capacitor_blocks():
    e, r, c = VoltageSource("E"), Resistor("R"), Capacitor("C")
    s = solve(Problem(GND >> e >> r >> Node() >> c >> GND, {e: 5, r: 100, c: "1u"}))
    assert (s(I(r)), s(U(c))) == (0, 5)


def test_contradiction():
    e, r = VoltageSource("E"), Resistor("R")
    with pytest.raises(Undetermined, match="contradict"):
        solve(Problem(loop(e, r), {e: 12, r: 10, I(r): 5}))


@GAP
def test_contradiction_names_the_clashing_data():
    raise NotImplementedError("ConflictingData: which data clash, by name — the prototype only says they do")


def test_underdetermined_is_said_when_asked():
    e, r1, r2 = VoltageSource("E"), Resistor("R_1"), Resistor("R_2")
    s = solve(Problem(GND >> e >> r1 >> Node() >> r2 >> GND, {e: 12, r1: 10}))
    with pytest.raises(Undetermined):
        s(Parameter(r2))


def test_two_solutions_from_power():
    e, r1, r2 = VoltageSource("E"), Resistor("R_1"), Resistor("R_2")
    with pytest.raises(Undetermined, match="2 solutions"):
        solve(Problem(loop(e, r1, r2), {e: 12, r2: 4, P(r1): 8}))


@GAP
def test_two_solutions_are_named():
    raise NotImplementedError("Ambiguous with the options (R_1 = 8 or 2) — the prototype only says there are two")


def test_three_sources_as_parallel_branches():
    # E1+R1 | R2 | E2+(R3 | J) between the top node and ground; superposition from the laws
    e1, e2, j, r1, r2, r3 = (
        VoltageSource("E_1"),
        VoltageSource("E_2"),
        CurrentSource("J"),
        Resistor("R_1"),
        Resistor("R_2"),
        Resistor("R_3"),
    )
    top, mid = Node("TOP"), Node("MID")
    # (the third branch: R3 ∥ J from the bottom to MID, then E2 turned, its + at MID, up to the top)
    circuit = (
        (GND >> e1 >> Node() >> r1 >> top)
        @ (GND >> r2 >> top)
        @ (GND >> r3 >> mid)
        @ (GND >> j >> mid)
        @ (top >> e2 >> mid)
    )
    p = Problem(circuit, {e1: 12, e2: 6, j: 1, r1: 2, r2: 4, r3: 6})
    total = solve(p)(I(r2))
    assert total == sp.Rational(-18, 11) and superposition(p, I(r2)).total == total


@GAP
def test_find_several_unknowns_and_missing_data():
    raise NotImplementedError("find + MissingData: what is missing to determine what is sought, and what would help")


@GAP
def test_hole_becomes_the_simplest_element():
    raise NotImplementedError("Hole: an unknown element, filled with the simplest that fits")


@GAP
def test_unknown_resistor_cannot_be_negative():
    raise NotImplementedError("an unknown resistance is positive: the prototype gives −34 Ω without a word")


def test_ammeter_reading_is_a_datum():
    e, r1, r2, r3, r4, a2 = (VoltageSource("E"), *(Resistor(f"R_{k}") for k in range(1, 5)), Ammeter())
    a, b, c = Node("A"), Node("B"), Node("C")
    # E, R1 = 3, then (R2 = 18 + ammeter) ∥ (R3 = 3 + R4 = 6); the ammeter reads 2 A
    circuit = (GND >> e >> a) @ (a >> r1 >> b) @ (b >> r2 >> c) @ (c >> a2 >> GND) @ (b >> r3 >> Node() >> r4 >> GND)
    s = solve(Problem(circuit, {r1: 3, r2: 18, r3: 3, r4: 6, I(a2): 2}))
    assert s(Parameter(e)) == 54


def test_meter_without_reading_reads_the_result():
    e, r1, r2, a1 = VoltageSource("E"), Resistor("R_1"), Resistor("R_2"), Ammeter()
    s = solve(Problem(loop(e, r1, a1, r2), {e: 12, r1: 4, r2: 2}))
    assert s(I(a1)) == 2


def test_vcvs_amplifies_the_voltage_it_senses():
    e, rin, rout, amp = VoltageSource("E"), Resistor("R_1"), Resistor("R_2"), VCVS("mu")
    inn, out = Node("in"), Node("out")
    s = solve(
        Problem(
            (GND >> e >> inn) @ (inn >> rin >> GND) @ at(amp, inn, GND, out, GND) @ (out >> rout >> GND),
            {e: 2, rin: 1000, rout: 50, "mu": 10},
        )
    )
    assert (s(V(out)), s(I(rout)), s(I(e))) == (20, sp.Rational(2, 5), sp.Rational(2, 1000))


def test_vccs_is_a_transconductance():
    e, g, r = VoltageSource("E"), VCCS("g"), Resistor("R")
    inn, out = Node("in"), Node("out")
    s = solve(Problem((GND >> e >> inn) @ at(g, inn, GND, out, GND) @ (out >> r >> GND), {e: 2, "g": "0.5", r: 10}))
    assert s(U(r)) == 10


def test_ccvs_and_cccs_sense_the_current_in_series():
    for kind, gain, want in ((CCVS, 3, 6), (CCCS, 10, 20)):
        e, r1, src, r2 = VoltageSource("E"), Resistor("R_1"), kind("k"), Resistor("R_2")
        a, b, out = Node("a"), Node("b"), Node("out")
        circuit = (GND >> e >> a) @ (a >> r1 >> b) @ at(src, b, GND, out, GND) @ (out >> r2 >> GND)
        s = solve(Problem(circuit, {e: 10, r1: 5, "k": gain, r2: 1}))
        assert s(I(e)) == 2 and (s(V(out)) if kind is CCVS else s(I(r2))) == want


def test_the_gain_is_found_from_the_data():
    e, rbe, beta, rc = VoltageSource("E"), Resistor("R_1"), CCCS("beta"), Resistor("R_2")
    inn, b, c = Node("in"), Node("b"), Node("c")
    circuit = (GND >> e >> inn) @ (inn >> rbe >> b) @ at(beta, b, GND, c, GND) @ (c >> rc >> GND)
    s = solve(Problem(circuit, {e: "10m", rbe: 1000, rc: 2000, U(rc): 2}))
    assert s(Parameter(beta)) == 100


@GAP
def test_ideal_transformer_coupled_inductors_three_phase():
    raise NotImplementedError("a transformer, coupled inductors, three-phase sources: kinds not written yet")


def test_phasor_strings():
    assert parse("230∠-120") == -115 - 115 * sp.sqrt(3) * sp.I  # (the same parser: data read once, as given)
    e, r = VoltageSource("E"), Resistor("R")
    s = solve(Problem(close(e >> r), {e: "10∠90", r: 1}), AC(sp.Integer(1)))
    assert s(I(r)) == 10 * sp.I  # (10∠90° V on 1 Ω: 10∠90° A)
