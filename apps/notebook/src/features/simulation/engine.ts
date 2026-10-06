// The circuit in time, in the page: electro's own engine (electro/engine.py, its Machine), printed as
// JavaScript at build time (engine.gen.js, by scripts/engine_js.py), on a program the Python side
// compiled (sympy wrote its residuals, Jacobian and readings as JavaScript). Here only what the page
// reads of it: `x` is what is seen of the circuit now (each point's potential, each element's voltage
// and currents), where `program.nodes`, `parts` and `flows` point.
import { limited_exp, limited_exp_slope, Machine, System } from "./engine.gen.js";

/** electro.simulate.StepFunction.to_json() */
export interface ProgramData {
  unknowns: string[];
  params: string[];
  initial: number[];
  states: [number, number | null][]; // param index, the most it may change in a step (null: it jumps)
  inputs: Record<string, number>; // name -> param index
  junctions: [number, number, number][]; // unknown index, n·V_T, V_crit
  constant: string; // fills A with the Jacobian's entries the unknowns do not change
  moving: string; // fills F with the residuals, A with the rest
  shape: object; // how they are eliminated (electro/sparse.py)
  update: string;
  seen: string[]; // what is read of a frame, by name ("V_A", "U_R_1", "R_1.a")
  see: string; // fills out with them
  nodes: Record<string, number>; // node -> index in seen
  parts: Record<string, Record<string, number>>; // element -> "U", "I", ... -> index in seen
  kinds: Record<string, string>; // element -> its kind
  flows: Record<string, number[]>; // element -> per terminal, in its order: index in seen of its current in
}

/** electro_notebook.kernel.live(): the program, and which node each wire and pin is. */
export interface LiveCircuit {
  program: ProgramData;
  wires: (string | null)[];
  pins: Record<string, (string | null)[]>;
}

type Body = (x: number[], p: number[], out: number[] | Float64Array) => void;
const compiled = (body: string, args: string) =>
  new Function("limexp", "dlimexp", `return function (${args}) {\n${body}\n}`)(limited_exp, limited_exp_slope);

export class NoConvergence extends Error {
  readonly time: number;
  constructor(time: number) {
    super(`NoConvergence at ${time}`);
    this.time = time;
  }
}

export type Schedule = (t: number) => [number, number][];

interface Engine {
  t: number;
  x: number[];
  p: number[];
  set(name: string, value: number): void;
  advance_to(target: number, dtMax: number, schedule: Schedule | null, onFrame: (() => void) | null): void;
  run(until: number, dtMax: number, schedule: Schedule | null, onFrame: (() => void) | null): void;
}

export class Simulation {
  readonly program: ProgramData;
  readonly n: number;
  private machine: Engine;
  private see: Body;
  private seen: Float64Array;
  private fresh = false;
  private where = new Map<string, number | null>(); // name → index in seen (null: 0 V), see at()

  constructor(program: ProgramData) {
    this.program = program;
    this.n = program.unknowns.length;
    this.machine = new Machine(
      { ...program, n: this.n },
      new System(program.shape, compiled(program.constant, "p, A"), compiled(program.moving, "x, p, F, A")),
      compiled(program.update, "x, p, out"),
    ) as Engine;
    this.see = compiled(program.see, "x, p, out");
    this.seen = new Float64Array(program.seen.length);
  }

  get t(): number {
    return this.machine.t;
  }

  /** What is seen of the circuit now. */
  get x(): Float64Array {
    if (!this.fresh) {
      this.see(this.machine.x, this.machine.p, this.seen);
      this.fresh = true;
    }
    return this.seen;
  }

  /** Each terminal's current now (into its element), where `program.flows` points. */
  get flowing(): Float64Array {
    return this.x;
  }

  flows(): Float64Array {
    return this.x;
  }

  setInput(name: string, value: number) {
    if (name in this.program.inputs) this.machine.set(name, value);
  }

  node(name: string): number {
    const i = this.program.nodes[name];
    return i === undefined ? 0 : this.x[i];
  }

  /** A quantity as the scope names it ("I_LED_1", "V_n3"), looked up once; 0 V where nothing is (ground). */
  at(name: string): number {
    let i = this.where.get(name);
    if (i === undefined) {
      const k = this.program.seen.indexOf(name);
      i = k >= 0 ? k : null;
      this.where.set(name, i);
    }
    return i === null ? 0 : this.x[i];
  }

  value(name: string): number {
    return this.at(name);
  }

  /** On to `target`, steps no longer than `dtMax`; `onStep` after each. */
  advanceTo(target: number, dtMax: number, schedule?: Schedule | null, onStep?: () => void) {
    this.stepping(() => this.machine.advance_to(target, dtMax, schedule ?? null, this.frame(onStep)));
  }

  /** From rest to `tEnd`; `onStep` also at t = 0 (after a first tiny step). */
  run(tEnd: number, dtMax: number, schedule?: Schedule | null, onStep?: () => void) {
    this.stepping(() => this.machine.run(tEnd, dtMax, schedule ?? null, this.frame(onStep)));
  }

  /** Raw, for a whole run handed back to Python: the unknowns and the parameters now. */
  get state(): { x: number[]; p: number[] } {
    return { x: this.machine.x, p: this.machine.p };
  }

  private frame(onStep?: () => void) {
    return () => {
      this.fresh = false;
      onStep?.();
    };
  }

  private stepping(go: () => void) {
    try {
      go();
    } catch (err) {
      const time = (err as { time?: number }).time;
      if (typeof time === "number") throw new NoConvergence(time);
      throw err;
    } finally {
      this.fresh = false;
    }
  }
}

/** What electro.simulate() calls in Pyodide (as ``js.electroSim.run``): the whole run at once, each frame's
 *  unknowns and parameters. */
export function runProgram(json: string, tEnd: number, dtMax: number, schedule?: Schedule | null) {
  const sim = new Simulation(JSON.parse(json));
  const times: number[] = [];
  const rows: number[] = [];
  const params: number[] = [];
  sim.run(tEnd, dtMax, schedule ?? null, () => {
    const { x, p } = sim.state;
    times.push(sim.t);
    for (const v of x) rows.push(v);
    for (const v of p) params.push(v);
  });
  return { t: Float64Array.from(times), rows: Float64Array.from(rows), params: Float64Array.from(params) };
}
