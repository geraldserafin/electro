import xml.etree.ElementTree as ET

from electro import *
from electro_render import schematic, steps

BOARD = (VoltageSource(12) + Resistor(2)) | Resistor(4) | ((Resistor(6) | CurrentSource(1)) + VoltageSource(6).transpose())


def svg_text(svg) -> str:
    root = ET.fromstring(svg)  # well-formed XML
    return "".join(root.itertext())


def test_schematic_is_valid_svg_with_labels():
    text = svg_text(schematic(BOARD))
    for label in ("R1 = 2 Ω", "E2 = 6 V", "J1 = 1 A"):
        assert label in text


def test_parallel_branches_default_to_vertical():
    svg = schematic(BOARD)
    width, height = float(ET.fromstring(svg).get("width")), float(ET.fromstring(svg).get("height"))
    assert width > height  # branches side by side


def test_currents_are_drawn_the_way_they_flow():
    text = svg_text(schematic(BOARD, BOARD.solve()))
    assert "I = 1.636 A ↓" in text and "U = 6.545 V" in text  # R2: no minus signs, arrow down


def test_solved_unknowns_and_holes_are_shown():
    c = loop(VoltageSource(12), Resistor(4), Hole())
    assert "X1: R = 2 Ω" in svg_text(schematic(c, c.solve(I_R_1=2)))
    d = supply(12) + Resistor(10) + shunt(Resistor()) + Resistor(5) + ground
    assert "R2 = 3.333 Ω" in svg_text(schematic(d, d.solve(I_R_1=1)))


def test_hand_drawn_schematics_are_drawn_as_placed():
    from electro_schematic import Element, Schematic, Wire

    sch = Schematic([Element("R_1", "resistor", (0, 0), 90, "10"), Element("g", "ground", (0, 4))],
                    [Wire([(0, -2), (0, 0)])])
    text = svg_text(schematic(sch))
    assert "R1 = 10 Ω" in text


def test_symbol_library_matches_the_model():
    from electro_schematic import KINDS
    from electro_render import symbol_library

    lib = symbol_library()
    assert set(lib["kinds"]) == set(KINDS)
    assert lib["kinds"]["resistor"]["pins"] == [[0, 0], [80, 0]]


def test_steps_are_data_with_latex():
    from electro.reasons import OhmsLaw

    shown = steps((supply(12) + Resistor(10) + Resistor() + ground).solve(I_R_1=0.5, find="R_2"))
    last = shown.steps[-1]
    assert last.chain == r"R_{2} = \frac{U_{R_{2}}}{I_{R_{2}}} = \frac{7}{0.5} = 14\,\mathrm{\Omega}"
    assert last.reason == OhmsLaw(Symbol("R_2"))
    assert shown.answer == [r"R_{2} = 14\,\mathrm{\Omega}"] and shown.missing is None
