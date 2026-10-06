"""The simulation engine for the page: electro's own (``electro/engine.py``) printed as JavaScript by
pscript, into ``src/features/simulation/engine.gen.js``. Run by ``bundle-python.mjs``."""

import ast
import pathlib
import sys

import pscript

repo = pathlib.Path(__file__).resolve().parents[3]
source = (repo / "packages/electro/src/electro/engine.py").read_text()
out = repo / "apps/notebook/src/features/simulation/engine.gen.js"

tree = ast.parse(source)
tree.body = [s for s in tree.body if not isinstance(s, ast.Import)]
for f in ast.walk(tree):
    if isinstance(f, ast.FunctionDef):  # JavaScript's own + * == and truthiness: fast
        f.body.insert(0, ast.parse("PSCRIPT_OVERLOAD = False").body[0])
body = pscript.py2js(ast.unparse(tree))
header = (
    "// Printed by scripts/engine_js.py from packages/electro/src/electro/engine.py: edit that one.\n"
    "/* eslint-disable */\n// @ts-nocheck\n"
    "const math = { exp: Math.exp, log: Math.log, isnan: Number.isNaN, inf: Infinity };\n"
    "class OverflowError extends Error {}\n"
    "function Exception() {}\n"
    "Exception.prototype = Object.create(Error.prototype);\n"
    "Exception.prototype.__init__ = function (message) { this.message = message; };\n"
)
names = ["Machine", "NoConvergence", "newton", "solve_linear", "limited_exp", "limited_exp_slope"]
out.write_text(header + body + f"\nexport {{ {', '.join(names)} }};\n")
print(f"engine: {out.relative_to(repo)}", file=sys.stderr)
