"""The run button: the test drawings as the page sends them (fixtures/problems.json, written by
schematic/problem.test.ts) solved by the kernel."""

import copy
import json
from pathlib import Path

from electro_notebook import kernel

PROBLEMS = json.loads(
    (Path(__file__).parent.parent / "src/features/schematic/fixtures/problems.json").read_text(encoding="utf-8")
)


def solve(problem: dict) -> dict:
    return json.loads(kernel.solve(json.dumps(problem)))


def problem(name: str, **values) -> dict:
    """A test drawing, with its elements' values (``None``: unknown) and its marks' set anew."""
    p = copy.deepcopy(PROBLEMS[name])
    for e in p["elements"]:
        if e["id"] in values:
            e["value"] = values[e["id"]]
    marks = {m[0]: m for m in p["marks"]}
    for id, value in values.items():
        if id in marks:
            marks[id][3] = value is not None
            p["given"] = [g for g in p["given"] if g[0] != marks[id][1]]
            if value is not None:
                p["given"].append([marks[id][1], value])
    return p


def test_arrows_of_elements_give_and_show_their_currents_and_voltages():
    got = solve(problem("arrows_of_elements"))
    assert got["results"]["E"]["value"] == "54 V" and got["results"]["E"]["solved"]
    assert got["results"]["i4"]["value"] == "-4 A"
    assert got["results"]["u"]["value"] == "18 V"


def test_a_labels_value_is_its_points_potential():
    got = solve(problem("label_potential", E1=None))["results"]
    assert got["E1"]["value"] == "6 V" and got["E1"]["solved"]
    assert got["L1"]["value"] == "4 V" and not got["L1"]["solved"]
    got = solve(problem("label_potential", L1=None, E1="12"))["results"]
    assert got["L1"]["value"] == "8 V" and got["L1"]["solved"]


def test_a_voltage_between_two_points():
    got = solve(problem("voltage_between"))["results"]
    assert got["E1"]["value"] == "100 V" and got["U1"]["value"] == "90 V" and not got["U1"]["solved"]
    got = solve(problem("voltage_between", U1=None, E1="50"))["results"]
    assert got["U1"]["value"] == "45 V" and got["U1"]["solved"]


def test_a_current_along_a_wire_both_ways_given_too():
    assert solve(problem("current_along"))["results"]["I1"]["value"] == "400 mA"
    assert solve(problem("current_along_back"))["results"]["I1"]["value"] == "-400 mA"
    got = solve(problem("current_along", I1="1", E1=None))["results"]
    assert got["E1"]["value"] == "30 V" and got["E1"]["solved"]
    assert solve(problem("current_beyond_junction"))["results"]["I1"]["value"] == "480 mA"


def test_a_terminal_on_a_wires_corner_and_what_is_sought():
    got = solve(problem("terminal_on_corner"))
    assert got["results"]["T1"]["value"] == "0 V"
    assert got["found"] == {"U:R1": "6 V", "value:E1": "6 V"}


def test_mesh_currents():
    got = solve(problem("mesh"))["results"]
    assert got["M1"]["value"] == "600 mA" and got["M2"]["value"] == "-300 mA"
    p = problem("mesh", E1=None)
    flipped = p["marks"][1][1]
    p["given"] = [[["sum", [[-k, q] for k, q in flipped[1]]], "1"]]
    assert solve(p)["results"]["E1"]["value"] == "40 V"


def test_a_meters_reading_is_a_datum():
    got = solve(problem("bridge", A_1="0"))["results"]["R_2"]
    assert got["value"] == "200 Ω" and got["solved"] and got["I"] == "33.33 mA"


def test_what_is_missing_and_what_clashes_is_said():
    [warning] = solve(problem("bridge"))["problems"]
    assert warning["kind"] == "warning" and warning["issue"]["type"] == "MissingData"
    [error] = solve(problem("label_potential", E1="12", L1="4"))["problems"]
    assert error["kind"] == "error" and error["issue"]["type"] == "ConflictingData"
    assert r"E1 = 12\,\mathrm{V}" in error["issue"]["values"]


def test_a_sine_source_on_paper_is_its_phasor():
    p = {
        "elements": [
            {
                "id": "E_1",
                "kind": "sine_source",
                "nodes": ["GND", "a"],
                "value": "10",
                "params": {"f": "50", "phase": 90},
            },
            {"id": "R_1", "kind": "resistor", "nodes": ["a", "GND"], "value": "5", "unit": "Ω"},
        ]
    }
    got = solve(p)
    assert got["problems"] == [] and got["results"]["R_1"]["I"] == "2 A ∠ 90°"


def test_a_hole_becomes_the_simplest_element_that_fits():
    p = {
        "elements": [
            {"id": "E_1", "kind": "voltage_source", "nodes": ["GND", "a"], "value": "12", "unit": "V"},
            {"id": "R_1", "kind": "resistor", "nodes": ["a", "b"], "value": "10", "unit": "Ω"},
            {"id": "X_1", "kind": "hole", "nodes": ["b", "GND"], "value": None},
        ],
        "given": [[["I", "R_1"], "0.5"]],
    }
    got = solve(p)["results"]["X_1"]
    assert got["value"] == "R = 14 Ω" and got["solved"]
