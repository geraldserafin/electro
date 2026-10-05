"""Memory (a flip-flop, Pre) and data in time (a clock)."""

import pytest
import sympy as sp
from electro.core import (
    GND,
    TIME,
    DFlipFlop,
    Node,
    Not,
    Problem,
    Resistor,
    Undetermined,
    V,
    VoltageSource,
    at,
    simulate,
    solve,
    square,
    when,
)


def _clocked():
    clk_src, ff, load = VoltageSource("E_clk"), DFlipFlop(), Resistor("R")
    clk, d, q = Node("CLK"), Node("D"), Node("Q")
    return clk_src, ff, load, clk, d, q, (GND >> clk_src >> clk) @ at(ff, d, clk, q, GND) @ (q >> load >> GND)


def test_a_flip_flop_takes_d_only_on_the_clocks_edge_and_holds_it_between():
    clk_src, _, load, _, d, q, circuit = _clocked()
    d_src = VoltageSource("E_d")
    period = sp.Rational(1, 1000)
    p = Problem(
        circuit @ (GND >> d_src >> d), {clk_src: square(5, period), d_src: when(TIME < 0.0018, 5, 0), load: 1000}
    )
    q_at = simulate(p, until=0.003, dt=1e-5)(V(q))
    assert [round(q_at(t)) for t in (0.0003, 0.0007, 0.0019, 0.0024, 0.0027)] == [0, 5, 5, 5, 0]


def test_a_flip_flop_and_a_not_gate_in_a_loop_halve_the_clock():
    clk_src, _, load, _, d, q, circuit = _clocked()
    p = Problem(circuit @ at(Not(), q, d, GND), {clk_src: square(5, sp.Rational(1, 1000)), load: 1000})
    q_at = simulate(p, until=0.005, dt=1e-5)(V(q))
    assert [round(q_at(t)) for t in (0.0003, 0.0008, 0.0018, 0.0028, 0.0038, 0.0048)] == [0, 5, 0, 5, 0, 5]


def test_on_paper_a_circuit_with_memory_is_said_to_need_its_past():
    clk_src, _, load, _, d, q, circuit = _clocked()
    with pytest.raises(Undetermined, match="memory"):
        solve(Problem(circuit @ (GND >> VoltageSource("E_d") >> d), {clk_src: 5, "E_d": 5, load: 1000}))
    e, r = VoltageSource("E"), Resistor("R")
    with pytest.raises(Undetermined, match="time"):
        solve(Problem(GND >> e >> r >> GND, {e: square(5, 1), r: 1}))
