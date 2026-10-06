"""Memory (a flip-flop, Pre) and data in time (a clock)."""

import pytest
import sympy as sp
from electro import GND, NOT, TIME, DFlipFlop, Node, Resistor, Undetermined, V, VoltageSource, square, when


def _clocked():
    clk_src, ff, load = (VoltageSource("E_clk"), DFlipFlop(), Resistor("R"))
    clk, d, q = (Node("CLK"), Node("D"), Node("Q"))
    return (clk_src, ff, load, clk, d, q, (GND >> clk_src >> clk) @ (ff >> d @ clk @ q @ Node()) @ (q >> load >> GND))


def test_a_flip_flop_takes_d_only_on_the_clocks_edge_and_holds_it_between():
    clk_src, _, load, _, d, q, circuit = _clocked()
    d_src = VoltageSource("E_d")
    period = sp.Rational(1, 1000)
    circuit, values = (
        circuit @ (GND >> d_src >> d),
        {clk_src: square(5, period), d_src: when(TIME < 0.0018, 5, 0), load: 1000},
    )
    trace = circuit.simulate(values, until=0.003, dt=1e-05)
    q_at = lambda t: trace.at(V(q), t)
    assert [round(q_at(t)) for t in (0.0003, 0.0007, 0.0019, 0.0024, 0.0027)] == [0, 5, 5, 5, 0]


def test_a_flip_flop_and_a_not_gate_in_a_loop_halve_the_clock():
    clk_src, _, load, _, d, q, circuit = _clocked()
    circuit, values = (circuit @ (NOT() >> q @ d), {clk_src: square(5, sp.Rational(1, 1000)), load: 1000})
    trace = circuit.simulate(values, until=0.005, dt=1e-05)
    q_at = lambda t: trace.at(V(q), t)
    assert [round(q_at(t)) for t in (0.0003, 0.0008, 0.0018, 0.0028, 0.0038, 0.0048)] == [0, 5, 0, 5, 0, 5]


def test_on_paper_a_circuit_with_memory_is_one_frame_from_rest():
    clk_src, _, load, _, d, q, circuit = _clocked()
    s = (circuit @ (GND >> VoltageSource("E_d") >> d)).final({clk_src: 5, "E_d": 5, load: 1000})
    assert s(V(q)) == 0 and s.time == sp.oo
    e, r = (VoltageSource("E"), Resistor("R"))
    with pytest.raises(Undetermined, match="time"):
        (GND >> e >> r >> GND).final({e: square(5, 1), r: 1})
