"""What the page asks beyond one frame (``electro_notebook.methods``), the problem as the page's data
(``netlist``), and LaTeX."""

import json

import pytest
import sympy as sp
from electro import (
    AC,
    GND,
    Ammeter,
    BadName,
    Capacitor,
    Hole,
    I,
    Inductor,
    Node,
    Open,
    Parameter,
    Problem,
    Resistor,
    U,
    V,
    Voltage,
    VoltageSource,
    Wire,
    solve,
)
from electro_notebook.latex import solution as latex
from electro_notebook.methods import fill, resistance, responses, spreads, swept
from electro_notebook.netlist import from_netlist, to_netlist

RUN = "__import__('os').system('echo pwned')"


def _between(piece_of, *values):
    """``piece_of(a, b)`` between two named points, nothing else: its resistance, values put in."""
    a, b = Node("A"), Node("B")
    piece, given = piece_of(a, b), dict(values)
    return resistance(Problem(piece, given), a, b)


def test_series_and_parallel_come_out_of_the_circuit():
    ra, rb, rc = Resistor("a"), Resistor("b"), Resistor("c")
    assert _between(lambda a, b: a >> ra >> (rb | rc) >> b, (ra, 10), (rb, 20), (rc, 30)) == 22
    ra, rb, rc = Resistor("a"), Resistor("b"), Resistor("c")
    assert _between(lambda a, b: a >> (ra | rb | rc) >> b, (ra, 6), (rb, 3), (rc, 2)) == 1


def test_an_impedance_in_ac():
    r, c = Resistor("R"), Capacitor("C")
    a, b = Node("A"), Node("B")
    z = resistance(Problem(a >> r >> c >> b, {r: 1, c: 1}), a, b, AC(sp.Integer(1)))
    assert sp.simplify(z - (1 - sp.I)) == 0
    r, ll = Resistor("R"), Inductor("L")
    z = resistance(Problem(a >> r >> ll >> b, {r: 1, ll: 1}), a, b, AC(sp.Integer(2)))
    assert sp.simplify(z - (1 + 2 * sp.I)) == 0


def test_a_divider_seen_from_its_output():
    e, r1, r2 = VoltageSource("E"), Resistor("R_1"), Resistor("R_2")
    out = Node("out")
    p = Problem((GND >> e >> r1 >> out) @ (out >> r2 >> GND), {e: 12, r1: 10, r2: 10})
    assert solve(p)(V(out)) == 6 and resistance(p, out, GND) == 5


def _rc():
    e, r, c = VoltageSource("E"), Resistor("R"), Capacitor("C")
    a = Node("A")
    return Problem((GND >> e >> r >> a) @ (a >> c >> GND), {e: 12, r: "1k", c: "1u"}), e, c, a


def test_bode_of_an_rc_low_pass():
    p, e, _, a = _rc()
    resp = responses(p, [V(a)], e)[V(a)]

    def at(f):
        return min(range(len(resp.f)), key=lambda k: abs(resp.f[k] - f))

    fc = 1 / (2 * 3.14159265 * 1e-3)
    assert resp.gain_db[0] == pytest.approx(0, abs=0.05)
    assert resp.gain_db[at(fc)] == pytest.approx(-3, abs=0.1) and resp.phase_deg[at(fc)] == pytest.approx(-45, abs=1)
    assert resp.gain_db[at(1e5)] - resp.gain_db[at(1e4)] == pytest.approx(-20, abs=0.5)
    [corner] = resp.cutoffs()
    assert corner == pytest.approx(fc, rel=0.01)


def test_a_value_swept():
    e, r1, r2 = VoltageSource("E"), Resistor("R_1"), Resistor("R_2")
    a = Node("A")
    p = Problem((GND >> e >> r1 >> a) @ (a >> r2 >> GND), {e: 12, r1: "1k"})
    assert swept(p, r2, (100, 5050, 10000), [V(a)])[V(a)][0] == sp.Rational(12 * 100, 1100)
    p, e, c, _ = _rc()
    out = swept(Problem(p.circuit, {**p.given, e: 1}), c, ("1u", "1n"), [U(c)], AC(sp.Integer(1000)))[U(c)]
    assert [abs(complex(x)) for x in out] == pytest.approx([1 / abs(1 + 1j), 1 / abs(1 + 1e-3j)])


def test_the_spread_of_a_divider():
    e, r1, r2 = VoltageSource("E"), Resistor("R_1"), Resistor("R_2")
    a = Node("A")
    p = Problem((GND >> e >> r1 >> a) @ (a >> r2 >> GND), {e: 12, r1: "10k", r2: "10k"})
    values = spreads(p, [V(a)], tol=0.05, runs=400)[V(a)]
    assert sum(values) / len(values) == pytest.approx(6, abs=0.03) and 5.7 <= min(values) and max(values) <= 6.3
    assert spreads(p, [V(a)], runs=50) == spreads(p, [V(a)], runs=50)
    assert len(set(spreads(p, [V(a)], tol={"C": 0.1}, runs=5)[V(a)])) == 1


def _with_hole(given_current):
    e, r, x = VoltageSource("E"), Resistor("R_1"), Hole("X")
    return Problem(GND >> e >> r >> Node() >> x >> GND, {e: 12, r: 10, I(r): given_current}), x


def test_a_hole_is_the_simplest_element_that_fits():
    filled = fill(*_with_hole("0.5"))
    assert filled.by.kind is Resistor and filled.solution(Parameter(filled.by)) == 14
    filled = fill(*_with_hole("-0.5"))
    assert filled.by.kind is VoltageSource and filled.solution(Parameter(filled.by)) == -17
    assert fill(*_with_hole("1,2")).by.kind is Wire
    e, r, x = VoltageSource("E"), Resistor("R_1"), Hole("X")
    filled = fill(Problem(~(e >> r >> x), {e: 12, r: 10, I(r): 0}), x)
    assert filled.by.kind is Open and filled.solution(U(filled.by)) == 12


def test_written_down_and_read_back_it_solves_the_same():
    e, r1, r2 = VoltageSource("E"), Resistor("R_1"), Resistor("R_2")
    b = Node("B")
    p = Problem((GND >> e >> r1 >> b) @ (b >> r2 >> GND), {e: 12, r1: 10, r2: 20}, [I(r1), V(b)])
    again = from_netlist(json.loads(json.dumps(to_netlist(p)))).problem
    assert list(solve(again).answers.values()) == list(solve(p).answers.values()) == [sp.Rational(2, 5), 8]


def test_a_meters_reading_is_written_down_as_its_value():
    e, r, a = VoltageSource("E"), Resistor("R"), Ammeter("A_1")
    data = to_netlist(Problem(~(e >> r >> a), {r: 3, I(a): 2}))
    assert [x.get("value") for x in data["elements"]] == [None, "3", "2"] and data["given"] == []
    again = from_netlist(data)
    assert solve(again.problem)(Voltage(again.elements["R"])) == 6


@pytest.mark.parametrize("name", [f"a+{RUN}", f"x)+{RUN}+(1", "R 1", "R'", "1R"])
def test_a_netlist_names_nothing_but_names(name):
    with pytest.raises(BadName):
        from_netlist({"elements": [{"id": name, "kind": "resistor", "nodes": ["GND", "A"]}]})
    if not name[0].isdigit():
        with pytest.raises(BadName):
            from_netlist({"elements": [{"id": "R_1", "kind": "resistor", "nodes": ["GND", name]}]})


def test_a_solution_in_latex():
    e, r = VoltageSource("E"), Resistor("R")
    s = solve(Problem(GND >> e >> r >> GND, {e: 12, r: 4}, [I(r)]))
    assert r"I_{R} = 3\,\mathrm{A}" in latex(s)
