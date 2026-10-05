// Runs the notebook kernel in real Pyodide (Node), the same way the browser worker does.
import { loadKernel } from "./kernel.mjs";

const kernel = await loadKernel();

const run = (code) => JSON.parse(kernel.run(code, "{}", "{}"));
const check = (name, ok, got) => {
  console.log(`${ok ? "ok  " : "FAIL"} ${name}`);
  if (!ok) {
    console.log(got);
    process.exitCode = 1;
  }
};

let out = run(`E, R_1, R_2 = VoltageSource("E"), Resistor("R_1"), Resistor("R_2")
c = Problem(loop(E, R_1, R_2), {E: 12, R_1: 10, I(R_1): 0.5}, [Parameter(R_2)])
sol = solve(c)
sol(Parameter(R_2))`);
check("solver", out[0]?.data === "$\\displaystyle 14$", out);
out = run("schematic(c, sol)");
check("schematic", out[0]?.type === "schematic" && out[0].shape?.loop?.length === 3, out);
out = run('bode(Problem(GND >> E >> R_1 >> Node("A") >> (C := Capacitor("C")) >> GND, {E: 1, R_1: 1000, C: 1e-6}))');
check("bode", out[0]?.type === "plot" && out[0].bode?.cutoffs?.length === 1, out);
out = run("steps(sol)");
check("steps", out[0]?.type === "solution" && JSON.stringify(out[0].data).includes("R_{2}"), out);
const led = {
  elements: [
    { id: "E_1", kind: "voltage_source", nodes: ["GND", "a"], value: "5", params: {} },
    { id: "R_1", kind: "resistor", nodes: ["a", "b"], value: "150", params: {} },
    { id: "LED_1", kind: "led", nodes: ["b", "GND"], value: null, params: {}, part: "red" },
  ],
};
const live = JSON.parse(kernel.live(JSON.stringify(led)));
check("live", live.program?.kinds?.LED_1 === "led" && live.program.kernel.includes("limexp"), live);
