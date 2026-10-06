import json

from electro_notebook import kernel


def run(code, **problems):
    """A cell run, the schematic cells' problems (as ``_loop`` writes them) by name."""
    return json.loads(kernel.run(code, json.dumps({k: json.loads(v) for k, v in problems.items()}), UNITS))


UNITS = json.dumps({"resistor": "Ω", "voltage_source": "V"})

LOOP = """E, R_1, R_2 = VoltageSource("E"), Resistor("R_1"), Resistor("R_2")
c = Problem(~(E >> R_1 >> R_2), {E: 12, R_1: 10, I(R_1): "0.5"}, [Parameter(R_2)])
sol = solve(c)"""


def test_cells_share_a_namespace_and_show_the_last_value():
    kernel.reset()
    assert run("x = 2") == []
    assert run("x * 21") == [{"type": "text", "data": "42"}]


def test_rich_outputs():
    kernel.reset()
    run(LOOP)
    [drawn] = run("schematic(c, sol)")
    assert drawn["type"] == "schematic" and drawn["netlist"]["elements"][0]["id"] == "E"
    assert drawn["results"]["R_2"]["value"] == "14 Ω" and drawn["results"]["R_2"]["solved"]
    [shown] = run("steps(sol)")
    assert shown["type"] == "solution" and shown["data"]["answer"] == [r"R_{2} = 14\,\mathrm{\Omega}"]
    assert {"type": "OhmsLaw", "label": "R_{2}"} in [s["reason"] for s in shown["data"]["steps"]]
    out = run("print('hej')\ndisplay(c)\nsol")
    assert [o["type"] for o in out] == ["stream", "schematic", "solution"]
    trace = run(
        'plot(simulate(Problem(~(E >> R_1 >> (C := Capacitor("C"))), {E: 5, R_1: 1000, C: 1e-6}), until=0.005), "U_C")'
    )
    assert trace[0]["type"] == "plot" and list(trace[0]["trace"]["series"]) == ["U_C"]
    [task] = run('task(c, "I_R_1", "Ile?")')
    assert task["type"] == "task" and task["unit"] == "A" and len(task["hashes"]) == 3


def test_errors_point_at_the_cell_line():
    kernel.reset()
    [out] = run(
        "a = 1\nsolve(Problem(~((E := VoltageSource('E')) >> (R := Resistor('R_1'))), {E: 12, R: 10, I(R): 5}))"
    )
    assert out["type"] == "error" and out["line"] == 2 and out["issue"]["type"] == "ConflictingData"
    assert out["issue"]["conditions"] == [r"I_{R_{1}} = 5\,\mathrm{A}"]  # math in LaTeX
    assert run("Resistr")[0]["data"].startswith("NameError")  # Python's own words


def test_warnings_are_shown():
    kernel.reset()
    assert run("import warnings\nwarnings.warn('uwaga')") == [{"type": "warning", "data": "uwaga"}]


def test_schematic_cells_are_available_by_name():
    kernel.reset()
    petla = _loop(("E_1", "voltage_source", "12"), ("R_1", "resistor", "4"))
    assert run('solve(schemat("petla"))("I_R_1")', petla=petla) == [{"type": "markdown", "data": "$\\displaystyle 3$"}]
    assert run('schemat("inny")', petla=petla)[0]["issue"] == {
        "type": "NoSuchSchematic",
        "name": "inny",
        "available": ["petla"],
    }


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


def test_code_view_read_back():
    # as the page writes it (schematic/code.ts), a value edited
    source = 'E_1 = VoltageSource("E_1")\nR_1 = Resistor("R_1")\nuklad = Problem(~(E_1 >> R_1), {E_1: 12, R_1: 6})'
    elements = json.loads(kernel.from_code(source, "uklad"))["netlist"]["elements"]
    assert [(e["id"], e["value"]) for e in elements] == [("E_1", "12"), ("R_1", "6")]
    # no variable called like the schematic: the last circuit the code defines
    assert "netlist" in json.loads(kernel.from_code('a = Resistor("R")\nb = ~(VoltageSource("E") >> a)', "x"))


def test_code_view_errors_name_the_line():
    error = json.loads(kernel.from_code("x = 1\nuklad = Resistr(1)", "uklad"))["error"]
    assert error["line"] == 2 and error["data"].startswith("NameError") and "issue" not in error  # Python's own words
    assert json.loads(kernel.from_code("x = 1", "uklad"))["error"]["issue"] == {
        "type": "NoCircuitInCode",
        "variable": "uklad",
    }


def test_a_schematic_is_a_variable_named_after_it():
    assert (
        kernel.variable("Układ 1") == "układ1"
        and kernel.variable("1 test") == "_1test"
        and kernel.variable("") == "uklad"
    )
    kernel.reset()
    drawing = _loop(("E_1", "voltage_source", "12"), ("R_1", "resistor", None))
    out = run(
        "sol = solve(Problem(układ1.circuit, {**układ1.given, I(układ1['R_1']): 2}))\nsol('R_1')",
        **{"Układ 1": drawing},
    )
    assert out == [{"type": "markdown", "data": "$\\displaystyle 6$"}]
    assert run("układ1", **{"Układ 1": drawing})[0]["type"] == "schematic"


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
