// A circuit running in time together with the Arduinos in it: the sketches run in short slices,
// each pin change reaches the circuit at the moment it happened, and after each slice the chips
// read what the circuit puts on their pins. What a device in the page will do later (an HC-SR04's
// echo) is scheduled: the circuit gets it exactly then, and the chips read their pins a moment after.
import { CLOCK, PIN_MODES, Uno } from "./arduino";
import { Simulation, type LiveCircuit } from "./engine";

export const SLICE = 1e-3; // s: how often the chips look at their pins; they run this far ahead of the circuit
const NUDGE = 1e-6; // s: after a scheduled change, the circuit one step on before the chips read it

export interface Board {
  label: string; // the Arduino's element id (ARD_1)
  uno: Uno;
  pins: Record<string, string | null>; // D13 → the node it is on
  ground: string | null;
}

export class Session {
  readonly sim: Simulation;
  readonly boards: Board[] = [];
  readonly circuit: LiveCircuit;

  constructor(circuit: LiveCircuit) {
    this.circuit = circuit;
    this.sim = new Simulation(circuit.program);
  }

  /** An Arduino in the circuit starts running ``hex`` (from reset, at the circuit's present time). */
  attach(label: string, hex: string) {
    const nodes = this.circuit.pins[label] ?? [];
    const pins = Object.fromEntries(Uno.pins.map((pin, i) => [pin, nodes[i] ?? null]));
    const uno = new Uno(hex);
    const board = { label, uno, pins, ground: nodes[Uno.pins.length + 1] ?? null };
    this.boards.push(board);
    this.offset.set(board, this.sim.t);
    for (const [pin, state] of uno.states()) this.drive(board, pin, state);
    return board;
  }

  // changes to come, in time order; scheduled at least SLICE ahead, a chip has not run past them yet
  private queue: { time: number; act: () => void }[] = [];

  /** ``act`` (setting the circuit's inputs) at ``time``, and the chips reading their pins right after. */
  schedule(time: number, act: () => void) {
    this.queue.push({ time, act });
    this.queue.sort((a, b) => a.time - b.time);
  }

  private offset = new WeakMap<Board, number>(); // the circuit's time when each chip was reset (a board replaced by a new sketch goes with it)

  private drive(board: Board, pin: string, state: keyof typeof PIN_MODES) {
    const [g, e] = PIN_MODES[state];
    this.sim.setInput(`${board.label}_${pin}_G`, g);
    this.sim.setInput(`${board.label}_${pin}_E`, e);
  }

  private sense(board: Board) {
    const ground = board.ground ? this.sim.node(board.ground) : 0;
    for (const [pin, node] of Object.entries(board.pins)) if (node) board.uno.sense(pin, this.sim.node(node) - ground);
  }

  /** On to ``target`` (seconds), steps no longer than ``dtMax``; ``onStep`` after each. */
  advanceTo(target: number, dtMax: number, onStep?: () => void) {
    const { sim } = this;
    while (sim.t < target - 1e-15) {
      const next = this.queue.length ? this.queue[0].time + NUDGE : Infinity;
      const end = Math.min(target, sim.t + SLICE, Math.max(next, sim.t + NUDGE));
      const events: { time: number; act: () => void }[] = [];
      for (const board of this.boards) {
        const start = this.offset.get(board)!;
        board.uno.runUntil(end - start);
        for (const e of board.uno.events) events.push({ time: start + e.cycle / CLOCK, act: () => this.drive(board, e.pin, e.state) });
        board.uno.events = [];
      }
      while (this.queue.length && this.queue[0].time < end) events.push(this.queue.shift()!);
      events.sort((a, b) => a.time - b.time);
      for (const e of events) {
        if (e.time > sim.t) sim.advanceTo(Math.min(e.time, end), dtMax, null, onStep);
        e.act();
      }
      sim.advanceTo(end, dtMax, null, onStep);
      for (const board of this.boards) this.sense(board);
    }
  }
}
