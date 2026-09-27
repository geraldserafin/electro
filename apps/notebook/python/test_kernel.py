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
    assert run("steps(sol)")[0]["type"] == "markdown"
    out = run("print('hej')\ndisplay(schematic(c))\n1")
    assert [o["type"] for o in out] == ["stream", "svg", "text"]


def test_errors_point_at_the_cell_line():
    kernel.reset()
    [out] = run("a = 1\nloop(VoltageSource(12), Resistor(10)).solve(I_R_1=5)")
    assert out["type"] == "error" and out["data"].startswith("linia 2: Contradiction")


def test_warnings_are_shown():
    kernel.reset()
    out = run("(supply(12) + Resistor(10) + Resistor() + ground).solve()")
    assert out[-1]["type"] == "warning" and "brakuje" in out[-1]["data"]


def test_schematic_cells_are_available_by_name():
    kernel.reset()
    from electro import Resistor, loop, VoltageSource
    from electro_schematic import layout

    drawing = layout(loop(VoltageSource(12), Resistor(4))).to_json()
    out = run('schemat("petla").to_circuit().solve()["R_1"].I', petla=drawing)
    assert out == [{"type": "markdown", "data": "$\\displaystyle 3$"}]
    assert "Nie ma schematu" in run('schemat("inny")', petla=drawing)[0]["data"]


def test_code_of_a_drawing():
    from electro import Resistor, VoltageSource, loop
    from electro_schematic import layout

    drawing = layout(loop(VoltageSource(12), Resistor(4))).to_json()
    assert kernel.code(drawing, "petla") == "petla = loop(VoltageSource(12), Resistor(4))"
    assert kernel.code(drawing, "nie nazwa") .startswith("uklad = ")


def test_symbols_for_the_editor():
    assert "resistor" in json.loads(kernel.symbols())["kinds"]
