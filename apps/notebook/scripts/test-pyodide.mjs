// Runs the notebook kernel in real Pyodide (Node), the same way the browser worker does.
import { readFileSync } from "node:fs";
import { loadPyodide } from "pyodide";

const bundle = JSON.parse(readFileSync(new URL("../public/py/bundle.json", import.meta.url), "utf8"));
const py = await loadPyodide();
await py.loadPackage(["sympy"]);
for (const [path, source] of Object.entries(bundle)) {
  const full = `/home/pyodide/lib/${path}`;
  py.FS.mkdirTree(full.slice(0, full.lastIndexOf("/")));
  py.FS.writeFile(full, source);
}
py.runPython("import sys; sys.path.insert(0, '/home/pyodide/lib')");
const kernel = py.pyimport("electro_notebook.kernel");

const run = (code) => JSON.parse(kernel.run(code, "{}"));
const check = (name, ok, got) => {
  console.log(`${ok ? "ok  " : "FAIL"} ${name}`);
  if (!ok) {
    console.log(got);
    process.exitCode = 1;
  }
};

let out = run("c = supply(12) + Resistor(10) + Resistor() + ground\nsol = c.solve(I_R_1=0.5)\nsol['R_2'].value");
check("solver", out[0]?.data === "$\\displaystyle 14$", out);
out = run("schematic(c, sol)");
check("schematic svg", out[0]?.type === "svg" && out[0].data.startsWith("<svg"), out);
out = run("bode(supply(1) + Resistor(1000) + node('A') + Capacitor(1e-6) + ground)");
check("bode svg", out[0]?.type === "svg" && out[0].data.includes("<polyline"), out);
out = run("steps(sol)");
check("steps markdown", out[0]?.type === "markdown" && out[0].data.includes("R_{2}"), out);
check("symbol library", "resistor" in JSON.parse(kernel.symbols()).kinds, null);
