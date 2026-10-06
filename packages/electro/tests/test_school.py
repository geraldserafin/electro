"""The library's school problems (test_school.py), each again on the prototype (electro), with the
same numbers."""

from functools import reduce
from operator import matmul

import pytest
import sympy as sp
from electro import (
    AC,
    CCCS,
    CCVS,
    GND,
    VCCS,
    VCVS,
    Ambiguous,
    Ammeter,
    Capacitor,
    Contradiction,
    Coupled,
    CurrentSource,
    Hole,
    I,
    Inductor,
    MissingData,
    Node,
    OpAmp,
    Open,
    P,
    Parameter,
    Problem,
    Resistor,
    Transformer,
    U,
    Undetermined,
    V,
    VoltageSource,
    Wire,
    between,
    blackbox,
    fill,
    resistance,
    respond,
    solve,
    superposition,
    sweep,
    thevenin,
    tolerance,
)
from electro import Capacitor as C
from electro.values import parse


def test_divider_with_unknown_resistor():
    e, r1, r2 = VoltageSource("E"), Resistor("R_1"), Resistor("R_2")
    s = solve(Problem(GND >> e >> r1 >> Node() >> r2 >> GND, {e: 12, r1: 10, I(r1): "0.5"}))
    assert (s(Parameter(r2)), s(U(r2)), -s(P(e))) == (14, 7, 6)


def test_givens_in_many_forms():
    for given in ("500m", "0,5 A"):
        e, r1, r2 = VoltageSource("E"), Resistor("R_1"), Resistor("R_2")
        assert solve(Problem(GND >> e >> r1 >> Node() >> r2 >> GND, {e: 12, r1: 10, I(r1): given}))(Parameter(r2)) == 14
    e, r1, r2 = VoltageSource("E"), Resistor("R_1"), Resistor("R_2")
    assert solve(Problem(GND >> e >> r1 >> Node() >> r2 >> GND, {e: 12, r1: 10, U(r1): 5}))(Parameter(r2)) == 14


def test_series_parallel_resistance():
    assert (
        resistance(blackbox(Resistor("a") >> (Resistor("b") | Resistor("c")))).subs({"a": 10, "b": 20, "c": 30}) == 22
    )
    r = resistance(blackbox(Resistor("a") | Resistor("b") | Resistor("c")))
    assert r.subs({"a": 6, "b": 3, "c": 2}) == 1
    assert parse("4k7") + parse("300") == 5000


def test_loop():
    e, r1, r2 = VoltageSource("E"), Resistor("R_1"), Resistor("R_2")
    s = solve(Problem(~(e >> r1 >> r2), {e: 12, r1: 4, r2: 2}))
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
    circuit = (GND >> e >> Node() >> r1 >> x) @ (x >> r2 >> out) @ (amp >> (GND @ x @ out))
    assert solve(Problem(circuit, {e: 1, r1: 1000, r2: 10000}))(V(out)) == -10


def test_ac_impedance():
    assert (
        resistance(blackbox(Resistor("R") >> C("C"), AC(sp.Integer(1))), AC(sp.Integer(1))).subs({"R": 1, "C": 1})
        == 1 - sp.I
    )
    assert (
        resistance(blackbox(Resistor("R") >> Inductor("L"), AC(sp.Integer(2))), AC(sp.Integer(2))).subs(
            {"R": 1, "L": 1}
        )
        == 1 + 2 * sp.I
    )


def test_ac_power_is_average():
    e, r, c = VoltageSource("E"), Resistor("R"), Capacitor("C")
    s = solve(Problem(GND >> e >> r >> Node() >> c >> GND, {e: 1, r: 1000, c: "1u"}), AC(sp.Integer(1000)))
    assert s(P(r)) == sp.Rational(1, 4000) and s(P(c)) == 0


def _rc(c_value="1u"):
    e, r, c = VoltageSource("E"), Resistor("R"), Capacitor("C")
    a = Node("A")
    return Problem((GND >> e >> r >> a) @ (a >> c >> GND), {e: 12, r: "1k", c: c_value}), e, r, c, a


def test_bode_rc_low_pass():
    p, e, _, _, a = _rc()
    resp = respond(p, V(a), e)

    def at(f):
        return min(range(len(resp.f)), key=lambda k: abs(resp.f[k] - f))

    fc = 1 / (2 * 3.14159265 * 1e-3)
    assert resp.gain_db[0] == pytest.approx(0, abs=0.05)
    assert resp.gain_db[at(fc)] == pytest.approx(-3, abs=0.1) and resp.phase_deg[at(fc)] == pytest.approx(-45, abs=1)
    assert resp.gain_db[at(1e5)] - resp.gain_db[at(1e4)] == pytest.approx(-20, abs=0.5)
    [corner] = resp.cutoffs()
    assert corner == pytest.approx(fc, rel=0.01)


def test_sweep_a_divider():
    e, r1, r2 = VoltageSource("E"), Resistor("R_1"), Resistor("R_2")
    a = Node("A")
    p = Problem((GND >> e >> r1 >> a) @ (a >> r2 >> GND), {e: 12, r1: "1k"})
    out = sweep(p, r2, (100, 5050, 10000), V(a))
    assert out.values == (100, 5050, 10000) and out.results[0] == sp.Rational(12 * 100, 1100)


def test_sweep_at_a_frequency_gives_amplitudes():
    p, e, _, c, _ = _rc()
    out = sweep(Problem(p.circuit, {**p.given, e: 1}), c, ("1u", "1n"), U(c), AC(sp.Integer(1000)))
    assert [abs(complex(x)) for x in out.results] == pytest.approx([1 / abs(1 + 1j), 1 / abs(1 + 1e-3j)])


def test_tolerance_of_a_divider():
    e, r1, r2 = VoltageSource("E"), Resistor("R_1"), Resistor("R_2")
    a = Node("A")
    p = Problem((GND >> e >> r1 >> a) @ (a >> r2 >> GND), {e: 12, r1: "10k", r2: "10k"})
    s = tolerance(p, V(a), tol=0.05, runs=400).stats()
    assert s["mean"] == pytest.approx(6, abs=0.03) and 5.7 <= s["min"] and s["max"] <= 6.3
    assert tolerance(p, V(a), tol=0.05, runs=400) == tolerance(p, V(a), tol=0.05, runs=400)
    assert tolerance(p, V(a), tol={"C": 0.1}, runs=5).stats()["std"] == 0


def test_dc_capacitor_blocks():
    e, r, c = VoltageSource("E"), Resistor("R"), Capacitor("C")
    s = solve(Problem(GND >> e >> r >> Node() >> c >> GND, {e: 5, r: 100, c: "1u"}))
    assert (s(I(r)), s(U(c))) == (0, 5)


def test_contradiction():
    e, r = VoltageSource("E"), Resistor("R")
    with pytest.raises(Undetermined, match="contradict"):
        solve(Problem(~(e >> r), {e: 12, r: 10, I(r): 5}))


def test_contradiction_names_the_clashing_data():
    e, r = VoltageSource("E"), Resistor("R")
    with pytest.raises(Contradiction) as err:
        solve(Problem(~(e >> r), {e: 12, r: 10, I(r): 5}))
    assert {e, r, I(r)} == set(err.value.data)


def test_underdetermined_is_said_when_asked():
    e, r1, r2 = VoltageSource("E"), Resistor("R_1"), Resistor("R_2")
    s = solve(Problem(GND >> e >> r1 >> Node() >> r2 >> GND, {e: 12, r1: 10}))
    with pytest.raises(Undetermined):
        s(Parameter(r2))


def test_two_solutions_from_power():
    e, r1, r2 = VoltageSource("E"), Resistor("R_1"), Resistor("R_2")
    with pytest.raises(Undetermined, match="2 solutions"):
        solve(Problem(~(e >> r1 >> r2), {e: 12, r2: 4, P(r1): 8}))


def test_two_solutions_are_named():
    e, r1, r2 = VoltageSource("E"), Resistor("R_1"), Resistor("R_2")
    with pytest.raises(Ambiguous) as err:
        solve(Problem(~(e >> r1 >> r2), {e: 12, r2: 4, P(r1): 8}))
    assert sorted(o[sp.Symbol("R_1")] for o in err.value.options) == [2, 8]
    e, r1, r2 = VoltageSource("E"), Resistor("R_1"), Resistor("R_2")
    assert solve(Problem(~(e >> r1 >> r2), {e: 12, r2: 4, P(r1): 8, U(r1): 2 * U(r2)}))(Parameter(r1)) == 8


def test_three_sources_as_parallel_branches():
    e1, e2, j, r1, r2, r3 = (
        VoltageSource("E_1"),
        VoltageSource("E_2"),
        CurrentSource("J"),
        Resistor("R_1"),
        Resistor("R_2"),
        Resistor("R_3"),
    )
    top, mid = Node("TOP"), Node("MID")
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


def _three_unknowns():
    e1, e2, j, r1, r2, r3 = (
        VoltageSource("E_1"),
        VoltageSource("E_2"),
        CurrentSource("J"),
        Resistor("R_1"),
        Resistor("R_2"),
        Resistor("R_3"),
    )
    top, mid = Node("TOP"), Node("MID")
    circuit = (
        (GND >> e1 >> Node() >> r1 >> top)
        @ (top >> r2 >> GND)
        @ (mid >> r3 >> GND)
        @ (GND >> j >> mid)
        @ (top >> e2 >> mid)
    )
    return circuit, {e1: 12, r2: 4, j: 1}, (r1, r2, r3, e2)


def test_find_several_unknowns():
    circuit, given, (r1, r2, r3, e2) = _three_unknowns()
    find = [Parameter(r1), Parameter(r3), Parameter(e2)]
    answers = solve(Problem(circuit, {**given, I(r1): 2, U(r2): 8, U(r3): 5}, find)).answers
    assert list(answers.values()) == [2, 5, -3]


def test_missing_data_says_what_would_help():
    circuit, given, (r1, r2, r3, e2) = _three_unknowns()
    s = solve(Problem(circuit, {**given, I(r1): 2, U(r2): 8}, [Parameter(r1), Parameter(r3), Parameter(e2)]))
    with pytest.raises(MissingData) as err:
        _ = s.answers
    assert err.value.needed == 1 and U(r3) in err.value.options
    assert err.value.found == {Parameter(r1): 2}


def test_missing_data_counts_redundant_givens_once():
    circuit, given, (r1, r2, r3, e2) = _three_unknowns()
    s = solve(Problem(circuit, {**given, U(r2): 8, I(r2): 2}, [Parameter(r1), Parameter(r3), Parameter(e2)]))
    with pytest.raises(MissingData) as err:
        _ = s.answers
    assert err.value.needed == 2


def _with_hole(given_current):
    e, r, x = VoltageSource("E"), Resistor("R_1"), Hole("X")
    return Problem(GND >> e >> r >> Node() >> x >> GND, {e: 12, r: 10, I(r): given_current}), x


def test_hole_becomes_the_simplest_element():
    filled = fill(*_with_hole("0.5"))
    assert filled.by.kind is Resistor and filled.solution(Parameter(filled.by)) == 14
    assert solve(filled.problem)(I(filled.by)) == sp.Rational(1, 2)


def test_hole_needs_a_source_when_current_flows_backwards():
    filled = fill(*_with_hole("-0.5"))
    assert filled.by.kind is VoltageSource and filled.solution(Parameter(filled.by)) == -17


def test_hole_can_be_a_plain_wire():
    assert fill(*_with_hole("1,2")).by.kind is Wire


def test_hole_with_no_current_is_a_break():
    e, r, x = VoltageSource("E"), Resistor("R_1"), Hole("X")
    filled = fill(Problem(~(e >> r >> x), {e: 12, r: 10, I(r): 0}), x)
    assert filled.by.kind is Open and filled.solution(U(filled.by)) == 12


def test_unknown_resistor_cannot_be_negative():
    e, r1, r2 = VoltageSource("E"), Resistor("R_1"), Resistor("R_2")
    with pytest.raises(Contradiction):
        solve(Problem(GND >> e >> r1 >> Node() >> r2 >> GND, {e: 12, r1: 10, I(r1): "-0.5"}))


def test_unknown_source_can_come_out_positive():
    e, r = VoltageSource("E"), Resistor("R")
    assert solve(Problem(~(e >> r), {r: 10, I(r): 5}))(Parameter(e)) == 50


def test_ammeter_reading_is_a_datum():
    e, r1, r2, r3, r4, a2 = (VoltageSource("E"), *(Resistor(f"R_{k}") for k in range(1, 5)), Ammeter())
    a, b, c = Node("A"), Node("B"), Node("C")
    circuit = (GND >> e >> a) @ (a >> r1 >> b) @ (b >> r2 >> c) @ (c >> a2 >> GND) @ (b >> r3 >> Node() >> r4 >> GND)
    s = solve(Problem(circuit, {r1: 3, r2: 18, r3: 3, r4: 6, I(a2): 2}))
    assert s(Parameter(e)) == 54


def test_meter_without_reading_reads_the_result():
    e, r1, r2, a1 = VoltageSource("E"), Resistor("R_1"), Resistor("R_2"), Ammeter()
    s = solve(Problem(~(e >> r1 >> a1 >> r2), {e: 12, r1: 4, r2: 2}))
    assert s(I(a1)) == 2


def test_vcvs_amplifies_the_voltage_it_senses():
    e, rin, rout, amp = VoltageSource("E"), Resistor("R_1"), Resistor("R_2"), VCVS("mu")
    inn, out = Node("in"), Node("out")
    s = solve(
        Problem(
            (GND >> e >> inn) @ (inn >> rin >> GND) @ (amp >> (inn @ GND @ GND @ out)) @ (out >> rout >> GND),
            {e: 2, rin: 1000, rout: 50, "mu": 10},
        )
    )
    assert (s(V(out)), s(I(rout)), s(I(e))) == (20, sp.Rational(2, 5), sp.Rational(2, 1000))


def test_vccs_is_a_transconductance():
    e, g, r = VoltageSource("E"), VCCS("g"), Resistor("R")
    inn, out = Node("in"), Node("out")
    s = solve(
        Problem((GND >> e >> inn) @ (g >> (inn @ GND @ GND @ out)) @ (out >> r >> GND), {e: 2, "g": "0.5", r: 10})
    )
    assert s(U(r)) == 10


def test_ccvs_and_cccs_sense_the_current_in_series():
    for kind, gain, want in ((CCVS, 3, 6), (CCCS, 10, 20)):
        e, r1, src, r2 = VoltageSource("E"), Resistor("R_1"), kind("k"), Resistor("R_2")
        a, b, out = Node("a"), Node("b"), Node("out")
        circuit = (GND >> e >> a) @ (a >> r1 >> b) @ (src >> (b @ GND @ GND @ out)) @ (out >> r2 >> GND)
        s = solve(Problem(circuit, {e: 10, r1: 5, "k": gain, r2: 1}))
        assert s(I(e)) == 2 and (s(V(out)) if kind is CCVS else s(I(r2))) == want


def test_the_gain_is_found_from_the_data():
    e, rbe, beta, rc = VoltageSource("E"), Resistor("R_1"), CCCS("beta"), Resistor("R_2")
    inn, b, c = Node("in"), Node("b"), Node("c")
    circuit = (GND >> e >> inn) @ (inn >> rbe >> b) @ (beta >> (b @ GND @ GND @ c)) @ (c >> rc >> GND)
    s = solve(Problem(circuit, {e: "10m", rbe: 1000, rc: 2000, U(rc): 2}))
    assert s(Parameter(beta)) == 100


def test_ideal_transformer_steps_down():
    e, tr, r = VoltageSource("E"), Transformer("n"), Resistor("R")
    a, b = Node("A"), Node("B")
    s = solve(
        Problem((GND >> e >> a) @ (tr >> (a @ GND @ GND @ b)) @ (b >> r >> GND), {e: 10, "n": 2, r: 10}),
        AC(sp.Integer(100)),
    )
    assert (s(U(r)), s(I(r))) == (5, sp.Rational(1, 2))
    assert complex(s(I(tr, "p1"))) == pytest.approx(0.25, abs=1e-6)
    e, r1, tr = VoltageSource("E"), Resistor("R"), Transformer("n")
    s_, a = Node("S"), Node("A")
    assert (
        solve(Problem((GND >> e >> s_) @ (s_ >> r1 >> a) @ (tr >> (a @ GND @ Node() @ GND)), {e: 10, r1: 5, "n": 2}))(
            I(r1)
        )
        == 2
    )


def test_coupled_inductors():
    e, r, m, rl = VoltageSource("E"), Resistor("R"), Coupled("M"), Resistor("R_L")
    a, b, c = Node("A"), Node("B"), Node("C")
    circuit = (GND >> e >> a) @ (a >> r >> b) @ (m >> (b @ GND @ GND @ c)) @ (c >> rl >> GND)
    s = solve(Problem(circuit, {e: 1, r: 1, m: {"": "1m", "L1": "2m", "L2": "3m"}, rl: "1G"}), AC(sp.Integer(1000)))
    i1 = complex(s(I(m, "p1")))
    assert i1 == pytest.approx(1 / (1 + 2j), rel=1e-6) and complex(s(V(c))) == pytest.approx(1j * i1, rel=1e-6)


def _three_phase(loads):
    """Three sources from a neutral, 120° apart — nothing of its own: three elements composed (F13)."""
    sources = [VoltageSource(f"E_{k}") for k in (1, 2, 3)]
    lines = [Node(f"L{k}") for k in (1, 2, 3)]
    given = {e: f"230∠{a}" for e, a in zip(sources, (0, -120, 120), strict=True)}
    return reduce(matmul, (GND >> e >> line for e, line in zip(sources, lines, strict=True))), lines, sources, given


def test_three_phase_star_and_delta():
    r = [Resistor(f"R_{k}") for k in (1, 2, 3)]
    supply, lines, sources, given = _three_phase(r)
    star = Node("S")
    s = solve(
        Problem(
            supply
            @ reduce(matmul, (line >> x >> star for line, x in zip(lines, r, strict=True)))
            @ (star >> Resistor("R_n") >> GND),
            {**given, **dict.fromkeys(r, 10), "R_n": 1},
        ),
        AC(sp.Integer(314)),
    )
    assert sp.simplify(s(V(star))) == 0
    r = [Resistor(f"R_{k}") for k in (1, 2, 3)]
    supply, lines, sources, given = _three_phase(r)
    star = Node("S")
    s = solve(
        Problem(
            supply @ reduce(matmul, (line >> x >> star for line, x in zip(lines, r, strict=True))),
            {**given, **dict(zip(r, (10, 20, 30), strict=True))},
        ),
        AC(sp.Integer(314)),
    )
    assert abs(complex(s(V(star)))) > 1
    r = [Resistor(f"R_{k}") for k in (1, 2, 3)]
    supply, (l1, l2, l3), sources, given = _three_phase(r)
    delta = (l1 >> r[0] >> l2) @ (l2 >> r[1] >> l3) @ (l3 >> r[2] >> l1)
    s = solve(Problem(supply @ delta, {**given, **dict.fromkeys(r, 10)}), AC(sp.Integer(314)))
    assert sp.simplify(sp.expand(s(U(r[0])) - 230 * sp.sqrt(3) * sp.exp(sp.I * sp.pi / 6), complex=True)) == 0


def test_phasor_strings():
    assert parse("230∠-120") == -115 - 115 * sp.sqrt(3) * sp.I
    e, r = VoltageSource("E"), Resistor("R")
    s = solve(Problem(~(e >> r), {e: "10∠90", r: 1}), AC(sp.Integer(1)))
    assert s(I(r)) == 10 * sp.I
