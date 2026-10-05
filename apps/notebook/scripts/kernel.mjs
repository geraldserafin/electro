// The notebook's kernel in real Pyodide (Node), loaded the way the browser worker loads it.
import { readFileSync } from "node:fs";
import { loadPyodide } from "pyodide";

export async function loadKernel() {
  const bundle = JSON.parse(readFileSync(new URL("../public/py/bundle.json", import.meta.url), "utf8"));
  const py = await loadPyodide();
  await py.loadPackage(["sympy"]);
  for (const [path, source] of Object.entries(bundle)) {
    const full = `/home/pyodide/lib/${path}`;
    py.FS.mkdirTree(full.slice(0, full.lastIndexOf("/")));
    py.FS.writeFile(full, source);
  }
  py.runPython("import sys; sys.path.insert(0, '/home/pyodide/lib')");
  return py.pyimport("electro_notebook.kernel");
}
