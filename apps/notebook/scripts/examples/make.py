"""Builds every course (apps/notebook/examples/): run from the repo root in devenv shell."""

import runpy
import sys
from pathlib import Path

here = Path(__file__).parent
sys.path.insert(0, str(here))
for name in sys.argv[1:] or ["course1", "course2", "course3", "course4"]:
    runpy.run_path(str(here / f"{name}.py"), run_name="__main__")
runpy.run_path(str(here.parent / "make_examples.py"), run_name="__main__")
