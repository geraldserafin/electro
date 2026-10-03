import json

from electro_notebook import kernel


def run(code, **schematics):
    return json.loads(kernel.run(code, json.dumps(schematics)))


def test_cells_share_a_namespace_and_show_the_last_value():
    kernel.reset()
    assert run("x = 2") == []
    assert run("x * 21") == [{"type": "text", "data": "42"}]


def test_rich_outputs():
    kernel.reset()
    run("c = supply(12) + Resistor(10) + Resistor() + ground\nsol = c.solve(I_R_1=0.5)")
    assert run("schematic(c, sol)")[0]["type"] == "svg"
    [shown] = run("steps(sol)")
    assert shown["type"] == "solution" and shown["data"]["steps"][-1]["reason"] == {"type": "OhmsLaw", "label": "R_{2}"}
    out = run("print('hej')\ndisplay(schematic(c))\n1")
    assert [o["type"] for o in out] == ["stream", "svg", "text"]


def test_errors_point_at_the_cell_line():
    kernel.reset()
    [out] = run("a = 1\nloop(VoltageSource(12), Resistor(10)).solve(I_R_1=5)")
    assert out["type"] == "error" and out["line"] == 2 and out["issue"]["type"] == "ConflictingData"
    assert out["issue"]["conditions"] == [r"I_{R_{1}} = 5\,\mathrm{A}"]  # math in LaTeX


def test_warnings_are_shown():
    kernel.reset()
    out = run("(supply(12) + Resistor(10) + Resistor() + ground).solve()")
    assert out[-1]["type"] == "warning" and out[-1]["issue"]["type"] == "Underdetermined"


def test_schematic_cells_are_available_by_name():
    kernel.reset()
    from electro import Resistor, VoltageSource, loop
    from electro_schematic import layout

    drawing = layout(loop(VoltageSource(12), Resistor(4))).to_json()
    out = run('schemat("petla").to_circuit().solve()["R_1"].I', petla=drawing)
    assert out == [{"type": "markdown", "data": "$\\displaystyle 3$"}]
    assert run('schemat("inny")', petla=drawing)[0]["issue"] == {
        "type": "NoSuchSchematic",
        "name": "inny",
        "available": ["petla"],
    }


def test_code_of_a_drawing():
    from electro import Resistor, VoltageSource, loop
    from electro_schematic import layout

    drawing = layout(loop(VoltageSource(12), Resistor(4))).to_json()
    assert kernel.code(drawing, "petla") == "petla = loop(VoltageSource(12), Resistor(4))"
    assert kernel.code(drawing, "nie nazwa").startswith("nienazwa = ")


def test_the_editors_symbol_file_is_up_to_date():
    from pathlib import Path

    from electro_render import symbol_library

    path = Path(__file__).parent.parent / "src/features/schematic/symbols.json"
    assert json.loads(path.read_text(encoding="utf-8")) == symbol_library(), "run scripts/make_symbols.py"


def test_symbols_for_the_editor():
    assert "resistor" in json.loads(kernel.symbols())["kinds"]


def test_simulate_a_drawing_with_measurements():
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parents[3] / "packages/electro-schematic/tests"))
    from test_schematic import bridge

    drawing = bridge()
    drawing.element("A_1").value = "0"  # the ammeter's reading
    out = json.loads(kernel.simulate(drawing.to_json()))
    r2 = out["results"]["R_2"]
    assert r2["value"] == "200 Ω" and r2["solved"] and r2["I"] == "33.33 mA" and out["problems"] == []


def test_simulate_reports_problems():
    from electro import Ammeter, Resistor, VoltageSource, loop
    from electro_schematic import layout

    drawing = layout(loop(VoltageSource(12), Resistor())).to_json()
    [problem] = json.loads(kernel.simulate(drawing))["problems"]  # R_1 unknown and no data
    assert problem["kind"] == "warning" and "R_{1}" in problem["issue"]["targets"]  # names in LaTeX
    contradiction = layout(loop(VoltageSource(12), Resistor(4), Ammeter(2))).to_json()
    [problem] = json.loads(kernel.simulate(contradiction))["problems"]
    assert problem["kind"] == "error" and r"E_{1} = 12\,\mathrm{V}" in problem["issue"]["values"]


def test_simulate_a_sine_source_with_phasors():
    from electro import Resistor, loop
    from electro.devices import SineSource
    from electro_schematic import layout

    out = json.loads(kernel.simulate(layout(loop(SineSource(10, 50, 90), Resistor(5))).to_json()))
    assert out["problems"] == [] and out["results"]["R_1"]["I"] == "2 A ∠ 90°"


def test_a_spice_netlist_in_the_code_view():
    source = 'uklad = from_spice("""* rc\nV1 in 0 SIN(0 1 1k)\nR1 in out 1k\nC1 out 0 100n\nD1 out 0 1N4148\n""")'
    out = json.loads(kernel.from_code(source, "uklad"))
    elements = {e["id"]: e for e in out["schematic"]["elements"]}
    assert elements["C1"]["value"] == "100n" and elements["D1"]["text"] == "1N4148"
    assert {e["text"] for e in elements.values() if e["kind"] == "label"} == {"in", "out"}


def test_frequency_of_a_drawing():
    from electro import Capacitor, Resistor, VoltageSource, loop
    from electro_schematic import layout

    out = json.loads(kernel.frequency(layout(loop(VoltageSource(1), Resistor(1000), Capacitor("1u"))).to_json()))
    assert "<polyline" in out["svg"] and "U" in out["svg"]  # the capacitor's voltage, no node named
    out = json.loads(kernel.frequency(layout(loop(VoltageSource(1), Resistor(1000))).to_json()))
    assert "no output" in out["error"]["data"]  # nothing named, nothing reactive


def test_sweep_and_spread_of_a_drawing():
    from electro import Resistor, VoltageSource, loop
    from electro_schematic import layout

    drawing = layout(loop(VoltageSource(12), Resistor("1k"), Resistor("2k"))).to_json()
    out = json.loads(kernel.sweep_plot(drawing, "R_2"))  # no range: 200 Ω to 20 kΩ
    assert "<polyline" in out["svg"] and "R<tspan" in out["svg"]
    assert "<polyline" in json.loads(kernel.sweep_plot(drawing, "R_2", "1k", "5k"))["svg"]
    assert "<rect" in json.loads(kernel.spread(drawing, 0.05))["svg"]
    unknown = layout(loop(VoltageSource(12), Resistor("1k"), Resistor())).to_json()
    assert json.loads(kernel.sweep_plot(unknown, "R_2"))["error"]["issue"]["type"] == "NoSweepRange"


def test_code_view_round_trip():
    from electro import Ammeter, Resistor, VoltageSource, loop
    from electro_schematic import Schematic, layout

    drawing = layout(loop(VoltageSource(12), Resistor(4) + Ammeter())).to_json()
    source = kernel.code(drawing, "uklad").replace("Resistor(4)", "Resistor(6)")
    back = Schematic.from_json(json.dumps(json.loads(kernel.from_code(source, "uklad"))["schematic"]))
    assert back.to_code("uklad") == source
    # no variable called like the schematic: the last circuit the code defines
    assert "schematic" in json.loads(kernel.from_code("a = Resistor(1)\nb = loop(VoltageSource(1), a)", "x"))


def test_code_view_errors_name_the_line():
    error = json.loads(kernel.from_code("x = 1\nuklad = Resistr(1)", "uklad"))["error"]
    assert error["line"] == 2 and error["data"].startswith("NameError") and "issue" not in error  # Python's own words
    assert json.loads(kernel.from_code("x = 1", "uklad"))["error"]["issue"] == {
        "type": "NoCircuitInCode",
        "variable": "uklad",
    }


def test_code_view_keeps_the_drawing_when_only_values_change():
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parents[3] / "packages/electro-schematic/tests"))
    from test_schematic import bridge

    old = bridge()
    source = kernel.code(old.to_json(), "mostek")
    changed = source.replace("Resistor(100)", "Resistor(150)", 1)
    back = json.loads(kernel.from_code(changed, "mostek", old.to_json()))["schematic"]
    assert [e["at"] for e in back["elements"]] == [list(e.at) for e in old.elements]
    assert "150" in [e["value"] for e in back["elements"]]
    # a new element in a net(...) (no automatic layout for it): says to add elements on the drawing
    grown = source.replace("Resistor(100)", "Resistor(100) + Resistor(1)", 1)
    assert json.loads(kernel.from_code(grown, "mostek", old.to_json()))["error"]["issue"]["type"] == "OnlyValuesInCode"


def test_a_schematic_is_a_variable_named_after_it():
    from electro import Resistor, VoltageSource, loop
    from electro_schematic import layout

    assert (
        kernel.variable("Układ 1") == "układ1"
        and kernel.variable("1 test") == "_1test"
        and kernel.variable("") == "uklad"
    )
    drawing = layout(loop(VoltageSource(12), Resistor())).to_json()
    kernel.reset()
    out = json.loads(
        kernel.run(
            "sol = układ1.solve(I_R_1=2)\ndisplay(schematic(układ1, sol))\nsol['R_1'].value",
            json.dumps({"Układ 1": drawing}),
        )
    )
    assert out[0]["type"] == "svg" and "6" in out[1]["data"]
    assert json.loads(kernel.run("układ1", json.dumps({"Układ 1": drawing})))[0]["type"] == "svg"
    assert kernel.code(drawing, "Układ 1").startswith("układ1 = ")


def _divider():
    from electro import Resistor, ground, supply
    from electro_schematic import layout

    return layout(supply(12) + Resistor(10) + Resistor(20) + ground).to_json()


def test_a_tasks_steps_are_solved_on_the_drawing():
    steps = [{"id": "rz", "value": "U_E_1 / I_E_1"}, {"id": "i", "value": "I_R_1"}, {"id": "x", "value": "I_R_9"}]
    got = json.loads(kernel.task_values(_divider(), json.dumps(steps)))["values"]
    assert got["rz"] == {"value": 30.0} and got["i"] == {"value": 0.4}
    assert got["x"]["error"]["issue"]["type"] == "NoSuchQuantity"  # said by that step, the others still solved


def test_a_circuit_from_data_is_drawn_and_never_run():
    def loop(id: str, kind: str = "resistor") -> str:
        return json.dumps(
            {
                "elements": [
                    {"id": "E1", "kind": "voltage_source", "value": "12", "nodes": ["0", "A"], "at": [[0, 4], [0, 0]]},
                    {"id": id, "kind": kind, "value": "10", "nodes": ["A", "0"], "at": [[0, 0], [4, 0]]},
                ],
                "wires": [[[4, 0], [4, 4], [0, 4]]],
            }
        )

    drawn = json.loads(kernel.from_drawing(loop("R1")))["schematic"]
    got = json.loads(kernel.task_values(json.dumps(drawn), json.dumps([{"id": "i", "value": "I_R1"}])))
    assert got["values"]["i"] == {"value": 1.2}
    evil = json.loads(kernel.from_drawing(loop("x)+__import__('os').system('x')")))
    assert evil["error"]["issue"]["type"] == "BadName"
    assert "UnknownKind" in json.loads(kernel.from_drawing(loop("Q1", "flux_capacitor")))["error"]["data"]


def test_a_circuit_drawn_as_its_picture_is_drawn_so():
    # the worksheet's task 3: E on the left, R on top, R1 over R2 in the middle, R3 on the right
    drawing = {
        "elements": [
            {"id": "E1", "kind": "voltage_source", "value": "45", "nodes": ["0", "A"], "at": [[0, 12], [0, 0]]},
            {"id": "R", "kind": "resistor", "value": "10", "nodes": ["A", "B"], "at": [[0, 0], [8, 0]]},
            {"id": "R1", "kind": "resistor", "value": "6", "nodes": ["B", "C"], "at": [[8, 0], [8, 6]]},
            {"id": "R2", "kind": "resistor", "value": "4", "nodes": ["C", "0"], "at": [[8, 6], [8, 12]]},
            {"id": "R3", "kind": "resistor", "value": "10", "nodes": ["B", "0"], "at": [[14, 0], [14, 12]]},
        ],
        # the bottom wire runs under R2's pin: touching, so joined
        "wires": [[[8, 0], [14, 0]], [[0, 12], [14, 12]]],
    }
    drawn = json.loads(kernel.from_drawing(json.dumps(drawing)))["schematic"]
    at = {e["id"]: (e["at"], e["rotation"]) for e in drawn["elements"]}
    assert at["R"] == ([2, 0], 0)  # in the middle of its 8 units, as on the picture
    assert at["R1"][1] == 90 and at["R3"][1] == 90  # standing, as drawn
    got = json.loads(kernel.task_values(json.dumps(drawn), json.dumps([{"id": "i", "value": "I_R"}])))
    assert abs(got["values"]["i"]["value"] - 45 / (10 + 10 * 10 / 20)) < 1e-9
    assert json.loads(kernel.from_drawing(json.dumps(drawing)))["rerouted"] is False
    # the right branch's top wire left out: the elements where they were, the wires laid by the nodes
    broken = json.loads(kernel.from_drawing(json.dumps({**drawing, "wires": [[[0, 12], [14, 12]]]})))
    assert broken["rerouted"] is True
    strict = json.loads(kernel.from_drawing(json.dumps({**drawing, "wires": [[[0, 12], [14, 12]]]}), True))
    assert strict["error"]["mismatch"] == ["node B is drawn as 2 separate pieces"]
    assert kernel.render_svg(json.dumps(drawn)).startswith("<svg")
    assert {e["id"]: e["at"] for e in broken["schematic"]["elements"]} == {e["id"]: e["at"] for e in drawn["elements"]}
    again = json.loads(kernel.task_values(json.dumps(broken["schematic"]), json.dumps([{"id": "i", "value": "I_R"}])))
    assert again["values"] == got["values"]
    # a terminal joined to nothing (its node's name alone): the circuit wrong, said so
    lone = {**drawing, "elements": [*drawing["elements"][:4], {**drawing["elements"][4], "nodes": ["B", "D"]}]}
    assert json.loads(kernel.from_drawing(json.dumps(lone)))["error"]["dangling"] == [
        "R3's terminal 2 (node D) is joined to nothing"
    ]
    # an open network (a divider: no source, its ends terminals): as drawn
    divider = {
        "elements": [
            {"id": "T1", "kind": "terminal", "nodes": ["A"], "at": [[0, 0]]},
            {"id": "R1", "kind": "resistor", "value": "100", "nodes": ["A", "B"], "at": [[4, 0], [4, 6]]},
            {"id": "R2", "kind": "resistor", "value": "100", "nodes": ["B", "C"], "at": [[4, 6], [4, 12]]},
            {"id": "T2", "kind": "terminal", "nodes": ["C"], "at": [[0, 12]]},
        ],
        "wires": [[[0, 0], [4, 0]], [[0, 12], [4, 12]]],
    }
    opened = json.loads(kernel.from_drawing(json.dumps(divider), True))
    assert opened["rerouted"] is False
    assert [e["kind"] for e in opened["schematic"]["elements"]].count("terminal") == 2
    # two nodes' pins on one point: no drawing of it
    clash = {**drawing, "elements": [*drawing["elements"][:4], {**drawing["elements"][4], "at": [[8, 6], [8, 12]]}]}
    assert json.loads(kernel.from_drawing(json.dumps(clash)))["error"]["mismatch"]
    # as a model may slip: drawn too small (scaled up, its shape kept), askew, wires as text or slanted
    small = {
        "elements": [{**e, "at": [[x / 2, y / 2] for x, y in e["at"]]} for e in drawing["elements"][:4]]
        + [{**drawing["elements"][4], "at": [[7, 0], [6, 6]]}],
        "wires": ["[4, 0], [7, 0]", [0, 6, 7, 6]],
    }
    again = json.loads(kernel.from_drawing(json.dumps(small)))["schematic"]
    assert {e["id"]: e["at"] for e in again["elements"]}["R"] == [2, 0]  # as before: scaled ×2
    tiny = {"elements": [{**drawing["elements"][1], "at": [[0, 0], [0, 0]]}], "wires": []}
    assert "error" in json.loads(kernel.from_drawing(json.dumps(tiny)))


def test_a_drawings_arrows_are_drawn_named_and_not_of_the_circuit():
    drawing = {
        "elements": [
            {"id": "E", "kind": "voltage_source", "value": "12", "nodes": ["0", "A"], "at": [[0, 8], [0, 0]]},
            {"id": "R1", "kind": "resistor", "value": "6", "nodes": ["A", "0"], "at": [[8, 0], [8, 8]]},
            {"id": "i", "kind": "current_arrow", "text": "I_1", "at": [[8, 5], [8, 6]]},
            {"id": "u", "kind": "voltage_arrow", "text": "U", "at": [[11, 8], [11, 0]]},
        ],
        "wires": [[[0, 0], [8, 0]], [[0, 8], [8, 8]]],
    }
    sch = json.loads(kernel.from_drawing(json.dumps(drawing), True))["schematic"]
    arrows = {e["id"]: e for e in sch["elements"] if e["kind"].endswith("_arrow")}
    assert (arrows["i"]["rotation"], arrows["i"]["text"]) == (90, "I_1")
    assert (arrows["u"]["rotation"], arrows["u"]["span"]) == (270, 8)  # up, 8 units long
    assert json.loads(kernel.simulate(json.dumps(sch)))["results"]["R1"]["I"] == "2 A"
    svg = kernel.render_svg(json.dumps(sch))
    assert '<tspan class="sub" dy="4">1</tspan>' in svg and ">U</text>" in svg


def test_an_arrows_value_is_given_and_one_without_shows_what_it_comes_to():
    # E unknown; I_2 = 2 A through R2 (its arrow down, the way R2 runs): E = 54 V, I_4 = 4 A
    drawing = {
        "elements": [
            {"id": "E", "kind": "voltage_source", "value": None, "nodes": ["0", "T"], "at": [[0, 9], [0, 3]]},
            {"id": "R1", "kind": "resistor", "value": "3", "nodes": ["T", "A"], "at": [[0, 0], [8, 0]]},
            {"id": "R2", "kind": "resistor", "value": "18", "nodes": ["A", "0"], "at": [[8, 2], [8, 8]]},
            {"id": "R3", "kind": "resistor", "value": "3", "nodes": ["A", "X"], "at": [[16, 0], [16, 5]]},
            {"id": "R4", "kind": "resistor", "value": "6", "nodes": ["X", "0"], "at": [[16, 5], [16, 12]]},
            {"id": "i2", "kind": "current_arrow", "text": "I_2", "value": "2", "of": "R2", "at": [[8, 9], [8, 10]]},
            {"id": "i4", "kind": "current_arrow", "text": "I_4", "of": "R4", "at": [[16, 14], [16, 13]]},
            {"id": "u", "kind": "voltage_arrow", "text": "U_1", "of": "R1", "at": [[8, -2], [0, -2]]},
        ],
        "wires": [
            [[0, 3], [0, 0]],
            [[8, 0], [16, 0]],
            [[8, 0], [8, 2]],
            [[0, 9], [0, 12], [16, 12]],
            [[8, 8], [8, 12]],
        ],
    }
    sch = json.loads(kernel.from_drawing(json.dumps(drawing), True))["schematic"]
    results = json.loads(kernel.simulate(json.dumps(sch)))["results"]
    assert results["E"]["value"] == "54 V" and results["E"]["solved"]
    assert results["i4"]["value"] == "-4 A"  # (its arrow up, the current down)
    assert results["u"]["value"] == "18 V"  # (to R1's left end, the higher one)
    steps = [{"id": "s", "label": "E", "unit": "V", "value": "U_E"}]
    assert json.loads(kernel.task_values(json.dumps(sch), json.dumps(steps)))["values"]["s"]["value"] == 54


def test_a_net_labels_value_is_its_nodes_potential_given_and_one_without_shows_it():
    drawing = {
        "elements": [
            {"id": "E1", "kind": "voltage_source", "value": None, "nodes": ["0", "T"], "at": [[0, 8], [0, 0]]},
            {"id": "R1", "kind": "resistor", "value": "10", "nodes": ["T", "A"], "at": [[0, 0], [6, 0]]},
            {"id": "R2", "kind": "resistor", "value": "20", "nodes": ["A", "0"], "at": [[6, 0], [6, 8]]},
        ],
        "wires": [[[6, 8], [0, 8]]],
    }
    sch = json.loads(kernel.from_drawing(json.dumps(drawing)))["schematic"]
    sch["elements"].append({"id": "L1", "kind": "label", "at": [6, 0], "rotation": 0, "value": "4", "text": "A"})
    got = json.loads(kernel.simulate(json.dumps(sch)))["results"]
    assert got["E1"]["value"] == "6 V" and got["E1"]["solved"]  # V_A = 4 V given: E found from it
    assert got["L1"] == {**got["L1"], "value": "4 V", "solved": False}
    sch["elements"][-1]["value"] = None
    sch["elements"][0]["value"] = "12"
    got = json.loads(kernel.simulate(json.dumps(sch)))["results"]
    assert got["L1"]["value"] == "8 V" and got["L1"]["solved"]  # what the node came to


def test_a_voltage_between_two_terminals_given_and_one_without_shows_it():
    # E (unknown) with Rw 2 inside, terminals T1 (top) and T2 (bottom), a load of 18 outside them
    drawing = {
        "elements": [
            {"id": "E1", "kind": "voltage_source", "value": None, "nodes": ["0", "a"], "at": [[0, 12], [0, 8]]},
            {"id": "Rw", "kind": "resistor", "value": "2", "nodes": ["a", "T"], "at": [[0, 8], [0, 0]]},
            {"id": "T1", "kind": "terminal", "nodes": ["T"], "at": [[4, 0]]},
            {"id": "T2", "kind": "terminal", "nodes": ["0"], "at": [[4, 12]]},
            {"id": "R1", "kind": "resistor", "value": "18", "nodes": ["T", "0"], "at": [[10, 0], [10, 12]]},
        ],
        "wires": [[[0, 0], [10, 0]], [[0, 12], [10, 12]]],
    }
    sch = json.loads(kernel.from_drawing(json.dumps(drawing)))["schematic"]
    arrow = {"id": "U1", "kind": "voltage_arrow", "at": [6, 12], "rotation": 270, "value": "90", "text": "U"}
    sch["elements"].append({**arrow, "between": ["T2", "T1"], "span": 12})
    got = json.loads(kernel.simulate(json.dumps(sch)))["results"]
    assert got["E1"]["value"] == "100 V" and got["E1"]["solved"]  # U = 90 V on 18 Ω: 5 A, E = 90 + 5·2
    assert got["U1"]["value"] == "90 V" and not got["U1"]["solved"]
    sch["elements"][-1]["value"] = None
    sch["elements"][0]["value"] = "50"
    got = json.loads(kernel.simulate(json.dumps(sch)))["results"]
    assert got["U1"]["value"] == "45 V" and got["U1"]["solved"]  # what it came to: 50 · 18/20
