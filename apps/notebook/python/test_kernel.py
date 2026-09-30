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


def test_frequency_of_a_drawing():
    from electro import Capacitor, Resistor, VoltageSource, loop
    from electro_schematic import layout

    out = json.loads(kernel.frequency(layout(loop(VoltageSource(1), Resistor(1000), Capacitor("1u"))).to_json()))
    assert "<polyline" in out["svg"] and "U" in out["svg"]  # the capacitor's voltage, no node named
    out = json.loads(kernel.frequency(layout(loop(VoltageSource(1), Resistor(1000))).to_json()))
    assert "no output" in out["error"]["data"]  # nothing named, nothing reactive


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
