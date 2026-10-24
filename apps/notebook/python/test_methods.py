"""What the page asks beyond one frame (``electro_notebook.methods``), and a circuit as the page's data
(``drawing``)."""

import json

import pytest
import sympy as sp
from electro import (
    AC,
    GND,
    Ammeter,
    BadName,
    Capacitor,
    CurrentSource,
    Hole,
    I,
    Inductor,
    Node,
    Open,
    Parameter,
    Resistor,
    U,
    V,
    Voltage,
    VoltageSource,
    Wire,
)
from electro_notebook.drawing import from_drawing, to_drawing
from electro_notebook.methods import Resistance, Thevenin, fill, resistance, responses, spreads, swept
from electro_notebook.steps import steps

RUN = "__import__('os').system('echo pwned')"


def _between(piece_of, *values):
    """``piece_of(a, b)`` between two named points, nothing else: its resistance, values put in."""
    a, b = Node("A"), Node("B")
    piece, given = piece_of(a, b), dict(values)
    return resistance(piece, given, a, b)


def test_series_and_parallel_come_out_of_the_circuit():
    ra, rb, rc = Resistor("a"), Resistor("b"), Resistor("c")
    assert _between(lambda a, b: a >> ra >> (rb | rc) >> b, (ra, 10), (rb, 20), (rc, 30)) == 22
    ra, rb, rc = Resistor("a"), Resistor("b"), Resistor("c")
    assert _between(lambda a, b: a >> (ra | rb | rc) >> b, (ra, 6), (rb, 3), (rc, 2)) == 1


def test_an_impedance_in_ac():
    r, c = Resistor("R"), Capacitor("C")
    a, b = Node("A"), Node("B")
    z = resistance(a >> r >> c >> b, {r: 1, c: 1}, a, b, AC(sp.Integer(1)))
    assert sp.simplify(z - (1 - sp.I)) == 0
    r, ll = Resistor("R"), Inductor("L")
    z = resistance(a >> r >> ll >> b, {r: 1, ll: 1}, a, b, AC(sp.Integer(2)))
    assert sp.simplify(z - (1 + 2 * sp.I)) == 0


def test_a_divider_seen_from_its_output():
    e, r1, r2 = VoltageSource("E"), Resistor("R_1"), Resistor("R_2")
    out = Node("out")
    c, v = (GND >> e >> r1 >> out) @ (out >> r2 >> GND), {e: 12, r1: 10, r2: 10}
    assert c.final(v)(V(out)) == 6 and resistance(c, v, out, GND) == 5


def _rc():
    e, r, c = VoltageSource("E"), Resistor("R"), Capacitor("C")
    a = Node("A")
    return (GND >> e >> r >> a) @ (a >> c >> GND), {e: 12, r: "1k", c: "1u"}, e, c, a


def test_bode_of_an_rc_low_pass():
    circuit, values, e, _, a = _rc()
    resp = responses(circuit, values, [V(a)], e)[V(a)]

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
    divider = (GND >> e >> r1 >> a) @ (a >> r2 >> GND)
    assert swept(divider, {e: 12, r1: "1k"}, r2, (100, 5050, 10000), [V(a)])[V(a)][0] == sp.Rational(12 * 100, 1100)
    circuit, values, e, c, _ = _rc()
    out = swept(circuit, {**values, e: 1}, c, ("1u", "1n"), [U(c)], AC(sp.Integer(1000)))[U(c)]
    assert [abs(complex(x)) for x in out] == pytest.approx([1 / abs(1 + 1j), 1 / abs(1 + 1e-3j)])


def test_the_spread_of_a_divider():
    e, r1, r2 = VoltageSource("E"), Resistor("R_1"), Resistor("R_2")
    a = Node("A")
    p = (GND >> e >> r1 >> a) @ (a >> r2 >> GND), {e: 12, r1: "10k", r2: "10k"}
    values = spreads(*p, [V(a)], tol=0.05, runs=400)[V(a)]
    assert sum(values) / len(values) == pytest.approx(6, abs=0.03) and 5.7 <= min(values) and max(values) <= 6.3
    assert spreads(*p, [V(a)], runs=50) == spreads(*p, [V(a)], runs=50)
    assert len(set(spreads(*p, [V(a)], tol={"C": 0.1}, runs=5)[V(a)])) == 1


def _with_hole(given_current):
    e, r, x = VoltageSource("E"), Resistor("R_1"), Hole("X")
    return GND >> e >> r >> Node() >> x >> GND, {e: 12, r: 10, I(r): given_current}, x


def test_a_hole_is_the_simplest_element_that_fits():
    filled = fill(*_with_hole("0.5"))
    assert isinstance(filled.by, Resistor) and filled.solution(Parameter(filled.by)) == 14
    filled = fill(*_with_hole("-0.5"))
    assert isinstance(filled.by, VoltageSource) and filled.solution(Parameter(filled.by)) == -17
    assert isinstance(fill(*_with_hole("1,2")).by, Wire)
    e, r, x = VoltageSource("E"), Resistor("R_1"), Hole("X")
    filled = fill(~(e >> r >> x), {e: 12, r: 10, I(r): 0}, x)
    assert isinstance(filled.by, Open) and filled.solution(U(filled.by)) == 12


def test_written_down_and_read_back_it_solves_the_same():
    e, r1, r2 = VoltageSource("E"), Resistor("R_1"), Resistor("R_2")
    b = Node("B")
    c, v = (GND >> e >> r1 >> b) @ (b >> r2 >> GND), {e: 12, r1: 10, r2: 20}
    again = from_drawing(json.loads(json.dumps(to_drawing(c, v, [I(r1), V(b)]))))
    found = again.final().answers(*again.find)
    assert list(found.values()) == list(c.final(v).answers(I(r1), V(b)).values()) == [sp.Rational(2, 5), 8]


def test_a_meters_reading_is_written_down_as_its_value():
    e, r, a = VoltageSource("E"), Resistor("R"), Ammeter("A_1")
    data = to_drawing(~(e >> r >> a), {r: 3, I(a): 2})
    assert [x.get("value") for x in data["elements"]] == [None, "3", "2"] and data["given"] == []
    again = from_drawing(data)
    assert again.final()(Voltage(again["R"])) == 6


@pytest.mark.parametrize("name", [f"a+{RUN}", f"x)+{RUN}+(1", "R 1", "R'", "1R"])
def test_a_drawing_names_nothing_but_names(name):
    with pytest.raises(BadName):
        from_drawing({"elements": [{"id": name, "kind": "resistor", "nodes": ["GND", "A"]}]})
    if not name[0].isdigit():
        with pytest.raises(BadName):
            from_drawing({"elements": [{"id": "R_1", "kind": "resistor", "nodes": ["GND", name]}]})


def test_several_things_are_sought_at_once_the_thevenin_resistance_too():
    e, r1, r2, rl, a = VoltageSource("E"), Resistor("R_1"), Resistor("R_2"), Resistor("R_L"), Node("A")
    c = GND >> e >> r1 >> a >> (r2 | rl) >> GND
    s = c.final({e: 12, r1: 4, r2: 4, rl: 10}, find=[I(rl), Thevenin(rl), Resistance(a, GND)])
    assert list(s.answers().values()) == [sp.Rational(1, 2), 2, sp.Rational(5, 3)]


def test_steps_solve_a_bridge_by_its_nodes_not_by_every_equation_at_once():
    e, (r1, r2, r3, r4, r5) = VoltageSource("E"), [Resistor(f"R_{i}") for i in range(1, 6)]
    n1, n2, n3, n4 = map(Node, ["n1", "n2", "n3", "n4"])
    c = (n1 >> e >> n2 >> r1 >> n3 >> r4 >> n1 >> r3 >> n4 >> r2 >> n2) @ (n3 >> r5 >> n4)
    shown = steps(c.final({e: 220, r1: 5, r2: 20, r3: 5, r4: 10, r5: 10}, find=[I(r5)]))["steps"]
    [system] = [s for s in shown if s["type"] == "SystemStep"]
    assert system["nodes"] == ["n3", "n4"] and len(system["equations"]) == 4
    assert [s["reason"]["type"] for s in shown[-6:-1]] == ["OhmsLaw"] * 5


def test_steps_join_resistors_in_series_and_parallel_when_one_source_drives_them():
    e, (r1, r2, r3, r4) = VoltageSource("E"), [Resistor(f"R_{i}") for i in range(1, 5)]
    c = GND >> e >> r1 >> Node() >> ((r2 >> r3) | r4) >> GND
    shown = steps(c.final({e: 20, r1: 2, r2: 3, r3: 5, r4: 8}, find=[I(r4)]))
    chains = [s["chain"] for s in shown["steps"]]
    assert [s["reason"]["type"] for s in shown["steps"][:3]] == ["Series", "Parallel", "Series"]
    assert chains[3] == r"I = \frac{E}{R_{z}} = \frac{20}{6} = 3.333\,\mathrm{A}"
    assert chains[-1].startswith(r"I_{R_{4}} = \frac{U_{234}}{R_{4}}") and shown["answer"] == [
        r"I_{R_{4}} = 1.667\,\mathrm{A}"
    ]


def test_a_current_source_gives_the_voltage_across_the_whole_first():
    j, r1, r2 = CurrentSource("J"), Resistor("R_1"), Resistor("R_2")
    shown = steps((GND >> j >> Node() >> (r1 | r2) >> GND).final({j: 2, r1: 6, r2: 3}))
    assert shown["steps"][1]["chain"] == r"U = J \cdot R_{z} = 2 \cdot 2 = 4\,\mathrm{V}"
