import json
from pathlib import Path

import pytest
from electro import Ammeter, Resistor, VoltageSource, loop

from electro_notes import FORMAT, VERSION, CodeCell, FormatError, Notebook, SchematicCell, load, loads, migrate
from electro_notes.__main__ import main

EXAMPLE = Path(__file__).parents[3] / "apps/notebook/examples/nieznane-i-dziury.electro.json"


def zadanie() -> Notebook:
    nb = Notebook("Zadanie 4")
    nb.add_markdown("# Zadanie 4\nPrąd $I_2 = 2\\,\\mathrm{A}$.")
    nb.add_schematic("Układ 1", loop(VoltageSource(label="E"), Resistor(3), (Resistor(18) + Ammeter(2)) | (Resistor(3) + Resistor(6))))
    nb.add_code("układ1.solve(find='E')")
    return nb


def test_round_trip():
    nb = zadanie()
    back = loads(nb.dumps())
    assert back.to_dict() == nb.to_dict()
    data = json.loads(nb.dumps())
    assert (data["format"], data["version"]) == (FORMAT, VERSION)
    assert [c["type"] for c in data["cells"]] == ["markdown", "schematic", "code"]


def test_schematics_are_circuits_by_name_or_variable():
    nb = zadanie()
    assert nb.schematic("Układ 1") is nb.schematic("układ1")
    assert nb.schematic("układ1").solve(find="E")["E"].value == 54
    with pytest.raises(KeyError, match="Są: Układ 1"):
        nb.schematic("Układ 2")
    with pytest.raises(ValueError, match="już jest"):
        nb.add_schematic("Układ 1", Resistor(1))


def test_version_1_is_migrated():
    v1 = {"version": 1, "title": "Stary", "codeInPdf": False, "cells": [
        {"id": "a", "type": "markdown", "source": "tekst"},
        {"id": "b", "type": "schematic", "name": "mostek", "schematic": {"elements": [], "wires": []},
         "data": "I_A_1 = 0", "outputs": [{"type": "markdown", "data": "| tabela |"}]},
    ]}
    nb = loads(json.dumps(v1))
    assert nb.title == "Stary" and nb.code_in_pdf is False and len(nb.id) == 32
    assert "data" not in nb.cells[1].extra and "outputs" not in nb.cells[1].extra  # gone with v2
    assert v1["cells"][1]["data"] == "I_A_1 = 0"  # the input is left alone
    assert migrate(v1)["version"] == VERSION


def test_unknown_keys_survive():
    data = zadanie().to_dict()
    data["tags"] = ["lab"]
    data["settings"]["theme"] = "dark"
    data["cells"][0]["collapsed"] = True
    again = loads(json.dumps(data)).to_dict()
    assert again["tags"] == ["lab"] and again["settings"]["theme"] == "dark" and again["cells"][0]["collapsed"]


@pytest.mark.parametrize("mutate, message", [
    (lambda d: d.update(version=99), "nowszej wersji"),
    (lambda d: d.update(format="coś"), "a nie notatnik"),
    (lambda d: d.pop("cells"), "brak listy"),
    (lambda d: d["cells"][0].update(type="wideo"), r"cells\[0\]\.type"),
    (lambda d: d["cells"][2].update(id=d["cells"][0]["id"]), r"cells\[2\]\.id: identyfikator .* się powtarza"),
    (lambda d: d["cells"][1].update(schematic={"elements": []}), r"cells\[1\]\.schematic"),
    (lambda d: d["cells"][1].update(name=" "), r"cells\[1\]\.name"),
])
def test_broken_files_say_what_and_where(mutate, message):
    data = zadanie().to_dict()
    mutate(data)
    with pytest.raises(FormatError, match=message):
        loads(json.dumps(data))
    with pytest.raises(FormatError, match="To nie jest JSON"):
        loads("{nie json")


def test_strip_outputs_keeps_the_document():
    nb = zadanie()
    code = next(c for c in nb.cells if isinstance(c, CodeCell))
    code.outputs, code.execution = [{"type": "text", "data": "E = 54 V"}], 1
    drawing = next(c for c in nb.cells if isinstance(c, SchematicCell))
    drawing.results, drawing.stale = {"E": {"value": "54 V"}}, True
    stripped = nb.strip_outputs().to_dict()
    assert stripped["cells"][2] == {"id": code.id, "type": "code", "source": code.source, "outputs": []}
    assert "results" not in stripped["cells"][1] and "stale" not in stripped["cells"][1]


def test_the_example_notebook(tmp_path):
    nb = load(EXAMPLE)
    assert nb.title and set(nb.schematics) == {"zarowka", "zadanie4"}
    assert nb.schematic("zadanie4").solve(find="E")["E"].value == 54
    copy = tmp_path / "copy.electro.json"
    nb.save(copy)
    assert load(copy).to_dict() | {"modified": None} == nb.to_dict() | {"modified": None}


def test_command_line(tmp_path, capsys):
    good, bad = tmp_path / "a.electro.json", tmp_path / "b.electro.json"
    zadanie().save(good)
    bad.write_text('{"version": 1}')
    assert main(["check", str(good), str(bad)]) == 1
    out = capsys.readouterr().out
    assert "Notebook('Zadanie 4': 1 markdown, 1 code, 1 schematic)" in out and "b.electro.json: BŁĄD" in out
    assert main(["strip", str(good)]) == 0
