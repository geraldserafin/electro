import pytest
from electro import *
from electro_schematic import Element, Schematic, Unsupported, Wire, layout

BOARD = (VoltageSource(12) + Resistor(2)) | Resistor(4) | ((Resistor(6) | CurrentSource(1)) + VoltageSource(6).transpose())


def bridge() -> Schematic:
    """A Wheatstone bridge drawn by hand, as the editor would save it."""
    return Schematic(
        elements=[
            Element("E_1", "voltage_source", (0, 12), 270, "10"),
            Element("R_1", "resistor", (4, 0), 90, "100"), Element("R_2", "resistor", (4, 6), 90, None),
            Element("R_3", "resistor", (12, 0), 90, "50"), Element("R_4", "resistor", (12, 6), 90, "100"),
            Element("A_1", "ammeter", (6, 5), 0),
            Element("gnd", "ground", (0, 12)),
        ],
        wires=[Wire([(0, 8), (0, 0), (4, 0)]), Wire([(4, 0), (12, 0)]), Wire([(4, 4), (4, 6)]), Wire([(12, 4), (12, 6)]),
               Wire([(4, 5), (6, 5)]), Wire([(10, 5), (12, 5)]), Wire([(4, 10), (4, 12)]),
               Wire([(12, 10), (12, 12)]), Wire([(0, 12), (12, 12)])],
    )


def results(solution):
    return {label: (solution[label].U, solution[label].I) for label in solution.system.parts}


def test_layout_round_trip_gives_the_same_physics():
    assert results(layout(BOARD).to_circuit().solve()) == results(BOARD.solve())


def test_layout_is_on_the_grid_and_keeps_labels():
    sch = layout(supply(12) + Resistor(10) + shunt(Resistor()) + ground)
    assert [e.id for e in sch.components()] == ["E_1", "R_1", "R_2"]
    assert all(isinstance(c, int) for e in sch.elements for c in e.at)
    assert sch.element("R_2").value is None and sch.element("R_1").value == "10"


def test_hand_drawn_bridge_solves():
    assert bridge().to_circuit().solve(I_A_1=0, find="R_2").answers == {"R_2": 200}


def test_a_wire_passing_over_a_pin_does_not_connect():
    sch = Schematic([Element("R_1", "resistor", (2, 0), 90, "1")], [Wire([(0, 2), (4, 2)])])
    assert sch.nodes()[(2, 0)] != sch.nodes()[(0, 2)] != sch.nodes()[(2, 4)]
    sch.wires = [Wire([(0, 0), (2, 0)])]  # a wire END on the pin does
    assert sch.nodes()[(0, 0)] == sch.nodes()[(2, 0)]


def test_t_junctions_connect_but_crossings_do_not():
    sch = Schematic(
        [Element("R_1", "resistor", (0, 0), 0, "1"), Element("R_2", "resistor", (2, -2), 90, "1")],
        [Wire([(4, 0), (6, 0)]), Wire([(2, 2), (2, 4)])],
    )
    nodes = sch.nodes()
    assert nodes[(2, 2)] != nodes[(0, 0)]  # R_2's bottom pin just sits on R_1's body: no contact
    sch.wires.append(Wire([(5, -3), (5, 3)]))  # crosses R_1's right wire without an end there
    assert sch.nodes()[(5, 3)] != sch.nodes()[(4, 0)]
    sch.wires.append(Wire([(2, 2), (5, 2)]))  # ends on the vertical wire: a T-junction
    assert sch.nodes()[(2, 4)] == sch.nodes()[(5, 3)]


def test_net_labels_connect_by_name():
    sch = Schematic(
        [Element("E_1", "voltage_source", (0, 0), 0, "5"), Element("R_1", "resistor", (10, 0), 0, "5"),
         Element("a", "label", (4, 0), text="X"), Element("b", "label", (10, 0), text="X"),
         Element("g1", "ground", (0, 0)), Element("g2", "ground", (14, 0))],
        [],
    )
    assert sch.to_circuit().solve()["R_1"].I == 1


def test_moving_an_element_drags_its_wires():
    sch = bridge()
    sch.move("A_1", (6, 3))
    assert Wire([(4, 5), (6, 5), (6, 3)]) in sch.wires and Wire([(10, 3), (10, 5), (12, 5)]) in sch.wires
    assert sch.to_circuit().solve(I_A_1=0, find="R_2").answers == {"R_2": 200}  # same circuit


def test_rotating_by_180_reverses_in_place_and_keeps_the_wires():
    original, sch = bridge(), bridge()
    for s in (original, sch):
        s.element("R_2").value = "200"
    sch.rotate("E_1", 180)
    assert sch.element("E_1").pins() == [(0, 8), (0, 12)]  # same two points, swapped
    assert sch.wires == original.wires
    assert original.to_circuit().solve()["R_1"].I == -sch.to_circuit().solve()["R_1"].I  # polarity reversed


def test_rotating_by_90_disconnects():
    sch = bridge()
    sch.rotate("R_4", 90)
    assert all(p not in {q for w in sch.wires for q in (w.points[0], w.points[-1])} for p in sch.element("R_4").pins())


def test_json_round_trip():
    sch = bridge()
    assert Schematic.from_json(sch.to_json()) == sch


def test_invalid_input_is_rejected():
    with pytest.raises(ValueError, match="poziomo albo pionowo"):
        Wire([(0, 0), (1, 1)])
    with pytest.raises(ValueError, match="Nieznany rodzaj"):
        Element("X", "transistor", (0, 0))
    with pytest.raises(Unsupported):
        layout(net((Resistor(1), "A", "B")))


def test_moving_a_wire_segment_keeps_its_ends():
    sch = bridge()
    sch.move_segment(0, 1, -1)  # top rail's horizontal part (0,0)-(4,0) moved up by one
    assert sch.wires[0] == Wire([(0, 8), (0, -1), (4, -1), (4, 0)])
    assert sch.to_circuit().solve(I_A_1=0, find="R_2").answers == {"R_2": 200}
    sch.move_segment(4, 0, 2)  # the single straight wire (4,5)-(6,5) bent down
    assert sch.wires[4] == Wire([(4, 5), (4, 7), (6, 7), (6, 5)])
