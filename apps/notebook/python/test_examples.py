"""Every example notebook runs top to bottom without an error (expected errors are caught in the cells)."""

import json
from pathlib import Path

import pytest

from electro_notebook import kernel

EXAMPLES = sorted((Path(__file__).parent.parent / "examples").glob("*.electro.json"))


def run_notebook(path: Path) -> list[tuple[str, list[dict]]]:
    notebook = json.loads(path.read_text(encoding="utf-8"))
    schematics = {c["name"]: json.dumps(c["schematic"]) for c in notebook["cells"] if c["type"] == "schematic"}
    kernel.reset()
    return [(c["source"], json.loads(kernel.run(c["source"], json.dumps(schematics))))
            for c in notebook["cells"] if c["type"] == "code"]


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_example_runs_without_errors(path):
    for source, outputs in run_notebook(path):
        errors = [o["data"] for o in outputs if o["type"] == "error"]
        assert not errors, f"{source}\n→ {errors}"


def test_unknowns_and_holes_give_the_described_answers():
    text = "\n".join(o["data"] for _, outs in run_notebook(Path(EXAMPLES[0]).parent / "nieznane-i-dziury.electro.json")
                     for o in outs)
    for expected in [
        "R_{2} = 50", "E_1 = 15 V", "E_2 = -4 V", "R_1 = 2 Ω", "brakuje 1 danej", "brakuje 1 danej",
        "tego nie da się uzyskać", "R_1 = 8 Ω albo R_1 = 2 Ω", "E*R_b/(R_a + R_b)", "R_2 = 200 Ω", "J_1 = 1 A",
        "X_1 → VoltageSource(14 V).transpose()", "X_1 → przewód", "X_1 → przerwa", ": R = 12 Ω",  # the drawing (subscripts are separate <tspan>s)
    ]:
        assert expected in text, expected
