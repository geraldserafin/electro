// The circuit in time, in the page: the same loop as electro.sim.Simulation, on a program the
// Python side compiled (sympy wrote its residuals and Jacobian as JavaScript). Kept step for step
// like the Python one, so both give the same numbers (within Newton's tolerance: when the inputs
// change, this one starts from the circuit as it last was with them); here it is JIT-compiled and
// fast enough to run live, next to an emulated Arduino.

/** electro.sim.Program.to_json() */
export interface ProgramData {
  unknowns: string[];
  params: string[];
  initial: number[];
  states: [number, number | null][]; // param index, the most it may change in a step (null: it jumps)
  inputs: Record<string, number>; // name -> param index
  junctions: [number, number, number][]; // unknown index, n·V_T, V_crit
  kernel: string;
  update: string;
  nodes: Record<string, number | null>; // node -> index in x (null: the reference, 0 V)
  parts: Record<string, Record<string, number>>; // element -> "U", "I", ... -> index in x
  kinds: Record<string, string>; // element -> class name
  flow?: string; // fills out with each terminal's current (from the node into the element)
  flows?: Record<string, number[]>; // element -> per terminal, in its order: index in flow's out
}

/** electro_notebook.kernel.live(): the program, and which node each wire and pin is. */
export interface LiveCircuit {
  program: ProgramData;
  wires: (string | null)[];
  pins: Record<string, (string | null)[]>;
}

const EXP_LIMIT = 80;
const limexp = (x: number) => (x <= EXP_LIMIT ? Math.exp(x) : Math.exp(EXP_LIMIT) * (1 + x - EXP_LIMIT));
const dlimexp = (x: number) => Math.exp(Math.min(x, EXP_LIMIT));
const RELTOL = 1e-6,
  VNTOL = 1e-6,
  MAX_NEWTON = 60;
const GUESSES = 64; // input combinations remembered (the most recent)

type Kernel = (x: Float64Array, p: Float64Array, F: Float64Array, J: Float64Array) => void;
type Update = (x: Float64Array, p: Float64Array, out: Float64Array) => void;

export class NoConvergence extends Error {
  readonly time: number;
  constructor(time: number) {
    super(`NoConvergence at ${time}`);
    this.time = time;
  }
}

/** ``A·x = b`` in place (A: n×n row by row), rows scaled, partial pivoting; false: singular. */
function solveLinear(A: Float64Array, b: Float64Array, n: number): boolean {
  for (let i = 0; i < n; i++) {
    let big = 0;
    for (let j = 0; j < n; j++) big = Math.max(big, Math.abs(A[i * n + j]));
    if (big === 0) big = 1;
    for (let j = 0; j < n; j++) A[i * n + j] /= big;
    b[i] /= big;
  }
  for (let col = 0; col < n; col++) {
    let pivot = col;
    for (let r = col + 1; r < n; r++) if (Math.abs(A[r * n + col]) > Math.abs(A[pivot * n + col])) pivot = r;
    if (Math.abs(A[pivot * n + col]) < 1e-300) return false;
    if (pivot !== col) {
      for (let j = col; j < n; j++) {
        const t = A[col * n + j];
        A[col * n + j] = A[pivot * n + j];
        A[pivot * n + j] = t;
      }
      const t = b[col];
      b[col] = b[pivot];
      b[pivot] = t;
    }
    const inv = 1 / A[col * n + col];
    for (let r = col + 1; r < n; r++) {
      const f = A[r * n + col] * inv;
      if (f === 0) continue;
      for (let j = col; j < n; j++) A[r * n + j] -= f * A[col * n + j];
      b[r] -= f * b[col];
    }
  }
  for (let i = n - 1; i >= 0; i--) {
    let s = b[i];
    for (let j = i + 1; j < n; j++) s -= A[i * n + j] * b[j];
    b[i] = s / A[i * n + i];
  }
  return true;
}

/** SPICE's junction limiting: along the exponential, never far past it in one go. */
function pnjlim(next: number, old: number, nvt: number, vcrit: number): number {
  if (next > vcrit && Math.abs(next - old) > 2 * nvt) {
    if (old > 0) {
      const arg = 1 + (next - old) / nvt;
      return arg > 0 ? old + nvt * Math.log(arg) : vcrit;
    }
    return nvt * Math.log(next / nvt);
  }
  return next;
}

export type Schedule = (t: number) => [number, number][];

export class Simulation {
  readonly n: number;
  x: Float64Array;
  p: Float64Array;
  t = 0;
  step = 0;
  switched = false; // a flip-flop changed in the last step
  private kernel: Kernel;
  private update: Update;
  private flow: Update;
  readonly flowing: Float64Array; // each terminal's current, as flow() last found them
  private F: Float64Array;
  private J: Float64Array;
  private after: Float64Array;
  // Newton's iterates: two buffers taking turns, so a step allocates nothing (thousands of steps a frame)
  private xa: Float64Array;
  private xb: Float64Array;
  private where = new Map<string, number | null>(); // quantity → index in x (null: 0 V), see at()
  // Newton's first guess when the inputs change: the circuit as it last was with those inputs. A PWM pin,
  // a multiplexed display go back and forth between a few of them, and from its own last state a step
  // converges in two iterations instead of fifteen (a LED turning on, walked up its exponential)
  private guesses = new Map<string, Float64Array>(); // the inputs' values → x
  private changed = false; // the inputs changed since the last step
  private inputIndices: number[];
  readonly program: ProgramData;

  constructor(program: ProgramData) {
    this.program = program;
    this.n = program.unknowns.length;
    this.x = new Float64Array(this.n);
    this.p = Float64Array.from(program.initial);
    this.kernel = new Function("limexp", "dlimexp", `return function (x, p, F, J) {\n${program.kernel}\n}`)(
      limexp,
      dlimexp,
    );
    this.update = new Function("limexp", "dlimexp", `return function (x, p, out) {\n${program.update}\n}`)(
      limexp,
      dlimexp,
    );
    this.flow = new Function("limexp", "dlimexp", `return function (x, p, out) {\n${program.flow ?? ""}\n}`)(
      limexp,
      dlimexp,
    );
    this.flowing = new Float64Array(Object.values(program.flows ?? {}).reduce((n, f) => n + f.length, 0));
    this.F = new Float64Array(this.n);
    this.J = new Float64Array(this.n * this.n);
    this.after = new Float64Array(program.states.length);
    this.inputIndices = Object.values(program.inputs).sort((i, j) => i - j);
    this.xa = new Float64Array(this.n);
    this.xb = new Float64Array(this.n);
  }

  setInput(name: string, value: number) {
    const i = this.program.inputs[name];
    if (i === undefined || this.p[i] === value) return;
    if (!this.changed) {
      // the inputs as they were: remember the circuit with them
      this.guesses.delete(this.inputsKey()); // (re-inserted: the map keeps the most recent last)
      this.guesses.set(this.inputsKey(), Float64Array.from(this.x));
      if (this.guesses.size > GUESSES) this.guesses.delete(this.guesses.keys().next().value!);
      this.changed = true;
    }
    this.p[i] = value;
  }

  private inputsKey(): string {
    let key = "";
    for (const i of this.inputIndices) key += `${this.p[i]},`;
    return key;
  }

  /** The value of a quantity ("V_A", "I_LED_1"); a node's potential by its name too. */
  value(name: string): number {
    const i = this.program.unknowns.indexOf(name);
    return i < 0 ? 0 : this.x[i];
  }

  /** Each terminal's current now (into its element), in ``flowing``. */
  flows(): Float64Array {
    this.flow(this.x, this.p, this.flowing);
    return this.flowing;
  }

  node(name: string): number {
    const i = this.program.nodes[name];
    return i === null || i === undefined ? 0 : this.x[i];
  }

  /** A quantity as the scope names it: an unknown ("I_LED_1") or a node's potential ("V_n3"), looked up once. */
  at(name: string): number {
    let i = this.where.get(name);
    if (i === undefined) {
      const k = this.program.unknowns.indexOf(name);
      i = k >= 0 ? k : name.startsWith("V_") ? (this.program.nodes[name.slice(2)] ?? null) : null;
      this.where.set(name, i);
    }
    return i === null ? 0 : this.x[i];
  }

  private newton(dt: number): Float64Array | null {
    const { n, p, F, J } = this;
    p[0] = dt;
    p[1] = this.t + dt;
    let x = this.xa,
      next = this.xb;
    x.set((this.changed && this.guesses.get(this.inputsKey())) || this.x);
    this.changed = false;
    for (let iteration = 1; iteration <= MAX_NEWTON; iteration++) {
      J.fill(0);
      this.kernel(x, p, F, J);
      for (let i = 0; i < n; i++) F[i] = -F[i];
      if (!solveLinear(J, F, n)) return null;
      for (let i = 0; i < n; i++) {
        if (Number.isNaN(F[i])) return null;
        next[i] = x[i] + F[i];
      }
      for (const [i, nvt, vcrit] of this.program.junctions) next[i] = pnjlim(next[i], x[i], nvt, vcrit);
      let done = true;
      for (let i = 0; i < n && done; i++)
        if (Math.abs(next[i] - x[i]) > RELTOL * Math.max(Math.abs(next[i]), Math.abs(x[i])) + VNTOL) done = false;
      const was = x;
      x = next;
      next = was;
      if (done && iteration > 1) return x;
    }
    return null;
  }

  /** Try one step of ``dt``: [accepted, how much of its allowed change a state used]; ``jump``: taken
   *  whatever the change, as long as Newton's method converged (see advanceTo). */
  advance(dt: number, jump = false): [boolean, number] {
    const x = this.newton(dt);
    if (!x) return [false, Infinity];
    const { states } = this.program;
    this.update(x, this.p, this.after);
    let change = 0;
    for (let k = 0; k < states.length; k++) {
      const [i, most] = states[k];
      if (most !== null) change = Math.max(change, Math.abs(this.after[k] - this.p[i]) / most);
    }
    if (change > 1 && !jump) return [false, change];
    this.x.set(x);
    this.t += dt;
    this.switched = false;
    for (let k = 0; k < states.length; k++) {
      const [i, most] = states[k];
      if (most === null && this.after[k] !== this.p[i]) this.switched = true;
      this.p[i] = this.after[k];
    }
    return [true, change];
  }

  /** Steps up to ``target``, as long as the states allow, at most ``dtMax``; in the shortest step a state
   *  may jump (see sim.py). */
  advanceTo(target: number, dtMax: number, schedule?: Schedule | null, onStep?: () => void) {
    const dtMin = dtMax * 1e-9;
    this.step = Math.min(this.step || Math.min(dtMax, 1e-6), dtMax);
    while (this.t < target - 1e-15) {
      const h = Math.min(this.step, target - this.t);
      if (schedule) for (const [i, value] of schedule(this.t)) this.p[i] = value;
      const [ok, change] = this.advance(h, h <= dtMin);
      if (!ok) {
        if (h <= dtMin) throw new NoConvergence(this.t);
        this.step = change === Infinity ? h / 4 : h / 2;
        continue;
      }
      onStep?.();
      if (this.switched) this.step = Math.max(dtMin, h / 8);
      else if (change < 0.25 && h >= this.step * 0.999) this.step = Math.min(dtMax, h * 2);
    }
  }

  /** From rest to ``tEnd``; ``onStep`` also at t = 0 (after a first tiny step). */
  run(tEnd: number, dtMax: number, schedule?: Schedule | null, onStep?: () => void) {
    if (schedule) for (const [i, value] of schedule(0)) this.p[i] = value;
    this.advanceTo(Math.min(1e-9, tEnd), dtMax, schedule);
    this.t = 0;
    onStep?.();
    this.advanceTo(tEnd, dtMax, schedule, onStep);
  }
}

/** What electro.sim.simulate() calls in Pyodide (as ``js.electroSim.run``): the whole run at once. */
export function runProgram(json: string, tEnd: number, dtMax: number, schedule?: Schedule | null) {
  const sim = new Simulation(JSON.parse(json));
  const times: number[] = [];
  const rows: number[] = [];
  sim.run(tEnd, dtMax, schedule ?? null, () => {
    times.push(sim.t);
    for (let i = 0; i < sim.n; i++) rows.push(sim.x[i]);
  });
  return { t: Float64Array.from(times), rows: Float64Array.from(rows) };
}
