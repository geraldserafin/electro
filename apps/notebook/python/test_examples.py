"""The example notebooks as built: ``scripts/examples/run.ts`` ran each as "Run all" (``pnpm test:examples``
runs them again), so what they keep is what their cells show — no error, and in the lesson on unknowns what
its text describes."""

import json
from pathlib import Path

import pytest

EXAMPLES = sorted((Path(__file__).parent.parent / "examples").glob("*/*.electro.json"))


def outputs(path: Path) -> list[dict]:
    notebook = json.loads(path.read_text(encoding="utf-8"))
    return [o for c in notebook["cells"] if c["type"] == "code" for o in c["outputs"]]


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_example_shows_no_error(path):
    assert not [o["data"] for o in outputs(path) if o["type"] == "error"]


def test_unknowns_and_holes_give_the_described_answers():
    shown = outputs(Path(__file__).parent.parent / "examples/3-biblioteka/03-niewiadome-i-dziury.electro.json")
    text = "\n".join(o["data"] for o in shown if isinstance(o.get("data"), str))
    for expected in ["$\\displaystyle -4$", "w dziurze: resistor = 12", "voltage_source -14"]:
        assert expected in text, expected
    assert [o["issue"]["type"] for o in shown if o["type"] == "issue"] == [
        "MissingData",
        "ConflictingData",
        "Ambiguous",
    ]
    steps = json.dumps(shown[0]["data"])
    assert "R_{2}" in steps and "OhmsLaw" in steps
