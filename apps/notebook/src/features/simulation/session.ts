// A circuit running in time together with the boards in it (chip.ts): the programs run in short slices,
// each pin change reaches the circuit at the moment it happened, and after each slice the chips
// read what the circuit puts on their pins. What a device in the page will do later (an HC-SR04's
// echo) is scheduled: the circuit gets it exactly then, and the chips read their pins a moment after.
// A pin on a node of its own (wired to nothing, and not on the scope) changes nothing else: its changes
// reach the circuit once a slice, as the pin is then — a program toggling it millions of times a second
// (Doom's sound, I²S by PIO) does not make the circuit step for each.
import type { Chip, Mode } from "./chip";
import { Simulation, type LiveCircuit } from "./engine";

export const SLICE = 1e-3; // s: how often the chips look at their pins; they run this far ahead of the circuit
const NUDGE = 1e-6; // s: after a scheduled change, the circuit one step on before the chips read it

export interface Board {
  label: string; // the board's element id (ARD_1, PICO_1)
  chip: Chip;
  pins: Record<string, string | null>; // D13 → the node it is on
  ground: string | null;
}

export class Session {
  readonly sim: Simulation;
  readonly boards: Board[] = [];
  readonly circuit: LiveCircuit;
  private terminals = new Map<string, number>(); // node → how many elements' terminals are on it
  private watched = new Set<string>(); // the nodes the scope and the meter show
  private lonely = new Map<Board, Set<string>>(); // each board's pins on a node of their own

  constructor(circuit: LiveCircuit) {
    this.circuit = circuit;
    this.sim = new Simulation(circuit.program);
    for (const nodes of Object.values(circuit.pins)) for (const n of nodes) if (n) this.terminals.set(n, (this.terminals.get(n) ?? 0) + 1);
  }

  /** The quantities the scope and the meter show ("V_n3": a node's potential): a pin on such a node is followed. */
  watch(names: readonly string[]) {
    this.watched = new Set(names.filter((n) => n.startsWith("V_")).map((n) => n.slice(2)));
    for (const board of this.boards) this.findLonely(board);
  }

  private findLonely(board: Board) {
    const pins = new Set(Object.entries(board.pins).filter(([, node]) =>
      !node || ((this.terminals.get(node) ?? 0) <= 1 && !this.watched.has(node))).map(([pin]) => pin));
    this.lonely.set(board, pins);
    board.chip.mute?.(pins);
  }

  /** A board in the circuit starts running, its chip just reset, at the circuit's present time. */
  attach(label: string, chip: Chip) {
    const nodes = this.circuit.pins[label] ?? [];
    const pins = Object.fromEntries(chip.pins.map((pin, i) => [pin, nodes[i] ?? null]));
    const board = { label, chip, pins, ground: nodes[nodes.length - 1] ?? null }; // (GND: a board's last terminal)
    this.boards.push(board);
    this.offset.set(board, this.sim.t);
    this.findLonely(board);
    for (const [pin, mode] of chip.initial()) this.drive(board, pin, mode);
    return board;
  }

  // changes to come, in time order; scheduled at least SLICE ahead, a chip has not run past them yet
  private queue: { time: number; act: () => void }[] = [];

  /** ``act`` (setting the circuit's inputs) at ``time``, and the chips reading their pins right after. */
  schedule(time: number, act: () => void) {
    this.queue.push({ time, act });
    this.queue.sort((a, b) => a.time - b.time);
  }

  private offset = new WeakMap<Board, number>();

  /** A board's own time (s): the circuit's when it was reset, plus how long its chip has run since. */
  clock(board: Board): number {
    return (this.offset.get(board) ?? 0) + board.chip.time;
  } // the circuit's time when each chip was reset (a board replaced by a new sketch goes with it)

  private drive(board: Board, pin: string, mode: Mode) {
    const [g, e] = board.chip.modes[mode];
    this.sim.setInput(`${board.label}_${pin}_G`, g);
    this.sim.setInput(`${board.label}_${pin}_E`, e);
  }

  private sense(board: Board) {
    const ground = board.ground ? this.sim.node(board.ground) : 0;
    for (const [pin, node] of Object.entries(board.pins)) if (node) board.chip.sense(pin, this.sim.node(node) - ground);
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
        board.chip.runUntil(end - start);
        const lonely = this.lonely.get(board)!;
        for (const e of board.chip.take()) {
          if (!lonely.has(e.pin)) events.push({ time: start + e.time, act: () => this.drive(board, e.pin, e.mode) });
        }
      }
      while (this.queue.length && this.queue[0].time < end) events.push(this.queue.shift()!);
      events.sort((a, b) => a.time - b.time);
      for (const e of events) {
        if (e.time > sim.t) sim.advanceTo(Math.min(e.time, end), dtMax, null, onStep);
        e.act();
      }
      for (const board of this.boards) { // (the lonely pins as they are now)
        const lonely = this.lonely.get(board)!;
        if (lonely.size) for (const [pin, mode] of board.chip.initial()) if (lonely.has(pin)) this.drive(board, pin, mode);
      }
      sim.advanceTo(end, dtMax, null, onStep);
      for (const board of this.boards) this.sense(board);
    }
  }
}
