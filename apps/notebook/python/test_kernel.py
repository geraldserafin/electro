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
    drawing = _loop(("E_1", "voltage_source", "12"), ("R_1", "resistor", "4"))
    assert kernel.code(drawing, "petla").splitlines() == [
        'E_1 = VoltageSource("E_1")',
        'R_1 = Resistor("R_1")',
        "petla = Problem(loop(E_1, R_1), {E_1: 12, R_1: 4})",
    ]
    assert "\nnienazwa = " in kernel.code(drawing, "nie nazwa")


def test_the_editors_symbol_file_is_up_to_date():
    from pathlib import Path

    from electro_render import symbol_library

    path = Path(__file__).parent.parent / "src/features/schematic/symbols.json"
    assert json.loads(path.read_text(encoding="utf-8")) == symbol_library(), "run scripts/make_symbols.py"


def test_symbols_for_the_editor():
    assert "resistor" in json.loads(kernel.symbols())["kinds"]


def test_a_spice_netlist_in_the_code_view():
    source = 'uklad = from_spice("""* rc\nV1 in 0 SIN(0 1 1k)\nR1 in out 1k\nC1 out 0 100n\nD1 out 0 1N4148\n""")'
    elements = {e["id"]: e for e in json.loads(kernel.from_code(source, "uklad"))["netlist"]["elements"]}
    assert elements["C1"]["value"] == "100n" and elements["D1"]["part"] == "1N4148"
    assert elements["R1"]["nodes"] == ["in", "out"]


def _loop(*elements) -> str:
    """Elements in one loop from ground, as the page sends them: each ``(id, kind, value)``."""
    nodes = ["GND", *(f"n{k}" for k in range(1, len(elements))), "GND"]
    units = {"voltage_source": "V", "resistor": "Ω", "capacitor": "F"}
    return json.dumps(
        {
            "elements": [
                {"id": id, "kind": kind, "value": value, "unit": units[kind], "nodes": [a, b]}
                for (id, kind, value), a, b in zip(elements, nodes, nodes[1:])
            ]
        }
    )


def test_frequency_of_a_drawing():
    rc = _loop(("E_1", "voltage_source", "1"), ("R_1", "resistor", "1000"), ("C_1", "capacitor", "1u"))
    bode = json.loads(kernel.frequency(rc))["bode"]
    assert list(bode["outputs"]) == ["U_C_1"] and bode["input"] == "E_1"
    assert abs(bode["cutoffs"][0] - 1 / (2 * 3.14159265 * 1e-3)) < 2
    plain = json.loads(kernel.frequency(_loop(("E_1", "voltage_source", "1"), ("R_1", "resistor", "1000"))))
    assert plain["error"]["issue"]["type"] == "NoOutput"


def test_sweep_and_spread_of_a_drawing():
    divider = _loop(("E_1", "voltage_source", "12"), ("R_1", "resistor", "1k"), ("R_2", "resistor", "2k"))
    trace = json.loads(kernel.sweep_plot(divider, "R_2"))["trace"]  # no range: 200 Ω to 20 kΩ
    assert (
        trace["x"] == {"name": "R_2", "unit": "Ω"}
        and trace["t"][0] == 200
        and set(trace["series"]) == {"U_R_2", "I_R_2"}
    )
    assert abs(trace["series"]["U_R_2"][0] - 12 * 200 / 1200) < 1e-9
    assert len(json.loads(kernel.sweep_plot(divider, "R_2", "1k", "5k"))["trace"]["t"]) == 100
    values = json.loads(kernel.spread(divider, 0.05))["histogram"]["values"]
    assert set(values) == {"U_R_1", "U_R_2"} and len(values["U_R_2"]) == 500
    unknown = _loop(("E_1", "voltage_source", "12"), ("R_1", "resistor", "1k"), ("R_2", "resistor", None))
    assert json.loads(kernel.sweep_plot(unknown, "R_2"))["error"]["issue"]["type"] == "NoSweepRange"


def test_code_view_round_trip():
    drawing = _loop(("E_1", "voltage_source", "12"), ("R_1", "resistor", "4"), ("C_1", "capacitor", "1u"))
    source = kernel.code(drawing, "uklad").replace("R_1: 4", "R_1: 6")
    back = json.loads(kernel.from_code(source, "uklad"))
    assert kernel.code(json.dumps(back["netlist"]), "uklad") == source
    assert [p["element"] for p in back["shape"]["loop"]] == ["E_1", "R_1", "C_1"]
    # no variable called like the schematic: the last circuit the code defines
    assert "netlist" in json.loads(kernel.from_code('a = Resistor("R")\nb = loop(VoltageSource("E"), a)', "x"))


def test_code_view_errors_name_the_line():
    error = json.loads(kernel.from_code("x = 1\nuklad = Resistr(1)", "uklad"))["error"]
    assert error["line"] == 2 and error["data"].startswith("NameError") and "issue" not in error  # Python's own words
    assert json.loads(kernel.from_code("x = 1", "uklad"))["error"]["issue"] == {
        "type": "NoCircuitInCode",
        "variable": "uklad",
    }


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
    assert "\nukład1 = " in kernel.code(_loop(("E_1", "voltage_source", "12")), "Układ 1")


def test_the_ais_solve_tool_on_a_drawing():
    divider = json.loads(_loop(("E_1", "voltage_source", "12"), ("R_1", "resistor", "10"), ("R_2", "resistor", "20")))
    steps = [{"id": "rz", "value": "U_E_1 / I_E_1"}, {"id": "i", "value": "I_R_1"}, {"id": "x", "value": "I_R_9"}]
    got = json.loads(kernel.task_values(json.dumps(divider), json.dumps(steps)))["values"]
    assert got["rz"] == {"value": 30.0} and got["i"] == {"value": 0.4}
    assert got["x"]["error"]["issue"]["type"] == "NoSuchQuantity"  # said by that step, the others still solved
    divider["elements"][0]["value"] = None
    divider["given"] = [[["I", "R_1"], "0.5"]]  # a mark's datum: E from it
    got = json.loads(kernel.task_values(json.dumps(divider), json.dumps([{"id": "e", "value": "U_E_1"}])))
    assert got["values"]["e"] == {"value": 15.0}
