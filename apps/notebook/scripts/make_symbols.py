"""Writes src/features/schematic/symbols.json from electro_render.symbol_library().

The editor draws schematics before Python has loaded, so it gets the symbols as a
static file; python/test_kernel.py checks the file is up to date. Run from the repo
root with PYTHONPATH set (e.g. in devenv shell) after changing electro_render/symbols.py.
"""

import json
from pathlib import Path

from electro_render import symbol_library

path = Path(__file__).parent.parent / "src/features/schematic/symbols.json"
path.write_text(json.dumps(symbol_library(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(path)
