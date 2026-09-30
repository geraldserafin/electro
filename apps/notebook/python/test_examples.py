"""Every example notebook runs top to bottom without an error (expected errors are caught in the cells)."""

import json
from pathlib import Path

import pytest
from electro_notebook import kernel

EXAMPLES = sorted((Path(__file__).parent.parent / "examples").glob("*/*.electro.json"))


def run_notebook(path: Path) -> list[tuple[str, list[dict]]]:
    notebook = json.loads(path.read_text(encoding="utf-8"))
    schematics = {c["name"]: json.dumps(c["schematic"]) for c in notebook["cells"] if c["type"] == "schematic"}
    kernel.reset()
    return [
        (c["source"], json.loads(kernel.run(c["source"], json.dumps(schematics))))
        for c in notebook["cells"]
        if c["type"] == "code"
    ]


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_example_runs_without_errors(path):
    for source, outputs in run_notebook(path):
        errors = [o["data"] for o in outputs if o["type"] == "error"]
        assert not errors, f"{source}\n→ {errors}"


def test_unknowns_and_holes_give_the_described_answers():
    outputs = [
        o
        for _, outs in run_notebook(
            Path(__file__).parent.parent / "examples/3-biblioteka/03-niewiadome-i-dziury.electro.json"
        )
        for o in outs
    ]
    text = "\n".join(o["data"] for o in outputs if isinstance(o["data"], str))
    issues = [o["issue"] for o in outputs if o["type"] == "issue"]
    for expected in [
        "E_1 = 15 V",
        "E_2 = -4 V",
        "R_1 = 2 Ω",
        "E*R_b/(R_a + R_b)",
        "R_2 = 200 Ω",
        "J_1 = 1 A",
        "X_1 → E = -14 V",
        "X_1 → R = 0 Ω",
        "X_1 → R = ∞",
        ": R = 12 Ω",  # the drawing (subscripts are separate <tspan>s)
    ]:
        assert expected in text, expected
    assert r"R_{2} = \frac{U_{R_{2}}}{I_{R_{2}}} = \frac{4}{0.08} = 50\,\mathrm{\Omega}" in json.dumps(
        outputs[0]["data"]
    ).replace("\\\\", "\\")
    assert [i["type"] for i in issues] == [
        "ConflictingData",
        "MissingData",
        "MissingData",
        "ConflictingData",
        "Ambiguous",
        "MissingData",
    ]
    assert [i.get("needed") for i in issues if i["type"] == "MissingData"] == [1, 1, 1]
    assert issues[4]["options"] == [[r"R_{1} = 8\,\mathrm{\Omega}"], [r"R_{1} = 2\,\mathrm{\Omega}"]]
