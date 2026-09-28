// A circuit running in time together with the Arduinos in it: the sketches run in short slices,
// each pin change reaches the circuit at the moment it happened, and after each slice the chips
// read what the circuit puts on their pins.
import { CLOCK, PIN_MODES, Uno } from "./arduino";
import { Simulation, type LiveCircuit } from "./engine";

const SLICE = 1e-3; // s: how often the chips look at their pins

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

  private offset = new Map<Board, number>(); // the circuit's time when each chip was reset

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
    if (!this.boards.length) return sim.advanceTo(target, dtMax, null, onStep);
    while (sim.t < target - 1e-15) {
      const end = Math.min(target, sim.t + SLICE);
      const events: { time: number; board: Board; pin: string; state: keyof typeof PIN_MODES }[] = [];
      for (const board of this.boards) {
        const start = this.offset.get(board)!;
        board.uno.runUntil(end - start);
        for (const e of board.uno.events) events.push({ time: start + e.cycle / CLOCK, board, pin: e.pin, state: e.state });
        board.uno.events = [];
      }
      events.sort((a, b) => a.time - b.time);
      for (const e of events) {
        if (e.time > sim.t) sim.advanceTo(Math.min(e.time, end), dtMax, null, onStep);
        this.drive(e.board, e.pin, e.state);
      }
      sim.advanceTo(end, dtMax, null, onStep);
      for (const board of this.boards) this.sense(board);
    }
  }
}
