"""code(circuit): readable electro code that rebuilds the same circuit."""

import sympy as sp

import electro
from electro import *

BOARD = (VoltageSource(12) + Resistor(2)) | Resistor(4) | ((Resistor(6) | CurrentSource(1)) + VoltageSource(6).transpose())


def rebuild(c):
    scope = {}
    exec(code(c), vars(electro) | {}, scope)
    return scope["uklad"]


def physics(c, **given):
    """Per label: |U|, |I| and P — independent of which way an element was read."""
    sol = c.solve(**given)
    return {label: (abs(sol[label].U), abs(sol[label].I), sol[label].P) for label in sol.system.parts}


def as_netlist(c):
    """The same circuit with the structure forgotten, like a drawing."""
    parts = c.netlist.parts
    names = electro.semantics._node_names(c.netlist)
    labels = electro.semantics._labels(parts)
    return net(*[(type(p)(p.value, label=l) if p.has_value else type(p)(label=l), *[names[n] for n in nodes])
                 for (p, nodes), l in zip(parts, labels)])


def test_branches_come_back_as_written():
    assert code(as_netlist(BOARD)) == (
        "uklad = (\n"
        "    (VoltageSource(12) + Resistor(2))\n"
        "    | Resistor(4)\n"
        "    | ((Resistor(6) | CurrentSource(1)) + VoltageSource(6).transpose())\n"
        ")"
    )


def test_single_source_circuits_become_loops():
    divider = supply(12) + Resistor(10) + shunt(Resistor()) + Resistor(5) + ground
    assert code(as_netlist(divider)) == "uklad = loop(VoltageSource(12), Resistor(10), Resistor() | Resistor(5))"
    assert code(loop(VoltageSource(12), Resistor(4), Hole())) == "uklad = loop(VoltageSource(12), Resistor(4), Hole())"


def test_open_circuits_and_values_round_trip():
    assert code(Resistor(1) + (Resistor(2) | Resistor(3))) == "uklad = Resistor(1) + (Resistor(2) | Resistor(3))"
    c = loop(VoltageSource("E"), Resistor("R"), Resistor(sp.Rational(18, 11)), Resistor("0,5"))
    assert code(c) == "uklad = loop(VoltageSource('E'), Resistor('R'), Resistor('18/11'), Resistor(0.5))"


def test_non_series_parallel_falls_back_to_net():
    bridge = net(
        (VoltageSource(10), "0", "A"),
        (Resistor(100), "A", "B"), (Resistor(), "B", "0"),
        (Resistor(50), "A", "C"), (Resistor(100), "C", "0"),
        (Ammeter(), "B", "C"),
    )
    text = code(bridge)
    assert text.startswith("uklad = net(\n    (VoltageSource(10), 'GND', 'A'),")
    assert rebuild(bridge).solve(I_A_1=0, find="R_2").answers == {"R_2": 200}


def test_labels_are_written_only_when_needed():
    c = loop(VoltageSource(12), Resistor(1, label="Rx"), Resistor(2))
    assert code(c) == "uklad = loop(VoltageSource(12), Resistor(1, label='Rx'), Resistor(2))"


def test_generated_code_is_the_same_circuit():
    for c, given in [
        (BOARD, {}),
        (as_netlist(BOARD), {}),
        (supply(12) + Resistor(10) + node("A") + shunt(Resistor(4)) + Resistor(5) + ground, {}),
        (loop(VoltageSource(12), Resistor(4) | Resistor(4), Resistor(1)), {}),
        (loop(VoltageSource(12), Resistor(4), Hole()), {"I_R_1": 2}),
    ]:
        assert physics(rebuild(c), **given) == physics(c, **given), code(c)
