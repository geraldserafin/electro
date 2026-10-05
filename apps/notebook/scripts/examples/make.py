"""Builds every course (apps/notebook/examples/), or the ones named: each lesson written (lib.py), then run
and checked (run.ts). Run from the repo root in devenv shell."""

import runpy
import subprocess
import sys
from pathlib import Path

here = Path(__file__).parent
app = here.parents[1]
sys.path.insert(0, str(here))
import lib  # noqa: E402 — after its folder is on the path

for name in sys.argv[1:] or ["course1", "course2", "course3", "course4"]:
    runpy.run_path(str(here / f"{name}.py"), run_name="__main__")
subprocess.run(["node", "scripts/bundle-python.mjs"], cwd=app, check=True)
subprocess.run(["node_modules/.bin/tsx", "scripts/examples/run.ts", *map(str, lib.WRITTEN)], cwd=app, check=True)
