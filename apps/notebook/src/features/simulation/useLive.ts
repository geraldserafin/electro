// A schematic cell running in time: its circuit compiled once (Python: kernel.live), then stepped
// in the page as the frames go by (engine.ts), with the Arduinos in it running their sketches
// (session.ts). What the board draws — the wires' voltages, the LEDs' glow, the readings — is taken
// from it every frame; switches, buttons and potentiometers set its inputs while it runs.
import { useAtomSet } from "@effect-atom/atom-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { failure } from "@/features/notes/sync";
import { kernel } from "@/features/python";
import type { ElementData, ElementResult, SchematicData } from "@/shared/model/types";
import type { Failure } from "@/shared/model/issues";
import { compileSketch } from "./atoms";
import { NoConvergence, type LiveCircuit } from "./engine";
import { si } from "./format";
import { Session } from "./session";

export type LiveStatus = "off" | "starting" | "running" | "paused";

/** What the board shows of the circuit at one moment. */
export interface LiveFrame {
  t: number;
  voltages: Record<string, number>; // node → V
  wires: (number | null)[]; // each wire's voltage (null: on no node)
  scale: number; // the largest |V| on the board, for the wires' colours
  leds: Record<string, number>; // LED id → brightness 0–1
  results: Record<string, ElementResult>; // readings next to the elements
  behind: boolean; // the page cannot keep up: time runs slower than asked
}

/** One trace on the scope: a quantity's name and its samples (t, value). */
export interface ScopeTrace {
  name: string;
  t: number[];
  v: number[];
}

/** An Arduino's sketch as it goes to the chip: compiling, running, or what the compiler said. */
export type SketchState =
  | { kind: "compiling" }
  | { kind: "running"; sketch: string }
  | { kind: "failed"; output: string }
  | { kind: "unavailable" | "signedOut" | "unreachable" };

const FRAME_BUDGET = 12; // ms of computing per frame at most (else the simulation falls behind)
const SCOPE_POINTS = 600;
export const SPEEDS = [1, 0.1, 0.01, 0.001];

/** The drawing without what may change while it runs (switches, positions, sketches): if that
 *  is the same, the circuit is too. */
function structure(sch: SchematicData): string {
  const inputs = new Set(["switch", "button", "potentiometer", "arduino"]);
  return JSON.stringify({ ...sch, elements: sch.elements.map((e) => (inputs.has(e.kind) ? { ...e, text: null } : e)) });
}

/** The inputs an element sets: [input name, value]. */
function inputsOf(e: ElementData, pressed: Set<string>): [string, number][] {
  if (e.kind === "switch") return [[`${e.id}_closed`, e.text === "closed" ? 1 : 0]];
  if (e.kind === "button") return [[`${e.id}_closed`, pressed.has(e.id) ? 1 : 0]];
  if (e.kind === "potentiometer") return [[`${e.id}_position`, Number(e.text ?? 0.5)]];
  return [];
}

/** The scope's quantities to start with: LEDs' currents, capacitors' voltages (at most four). */
function defaultScope(circuit: LiveCircuit): string[] {
  const { kinds, unknowns } = circuit.program;
  const leds = Object.keys(kinds).filter((k) => kinds[k] === "LED").map((k) => `I_${k}`);
  const caps = Object.keys(kinds).filter((k) => kinds[k] === "Capacitor").map((k) => `U_${k}`);
  return [...caps, ...leds].filter((n) => unknowns.includes(n)).slice(0, 4);
}

export function useLive(schematic: SchematicData) {
  const [status, setStatus] = useState<LiveStatus>("off");
  const [error, setError] = useState<Failure | null>(null);
  const [frame, setFrame] = useState<LiveFrame | null>(null);
  const [speed, setSpeed] = useState(1);
  const [scope, setScope] = useState<string[]>([]);
  const [traces, setTraces] = useState<ScopeTrace[]>([]);
  const [serial, setSerial] = useState("");
  const [sketches, setSketches] = useState<Record<string, SketchState>>({});
  const compile = useAtomSet(compileSketch, { mode: "promiseExit" });

  const session = useRef<Session | null>(null);
  const circuit = useRef<LiveCircuit | null>(null);
  const built = useRef<string>(""); // structure() of the drawing the session was compiled from
  const pressed = useRef(new Set<string>());
  const latest = useRef(schematic);
  latest.current = schematic;
  const speedRef = useRef(speed);
  speedRef.current = speed;
  const scopeRef = useRef(scope);
  scopeRef.current = scope;
  const history = useRef(new Map<string, ScopeTrace>());
  const serialText = useRef("");
  const statusRef = useRef(status);
  statusRef.current = status;
  // each LED's charge since the board was last drawn: its glow is the average current, so PWM dims it
  const glow = useRef({ since: 0, last: 0, charge: new Map<string, number>() });

  const applyInputs = useCallback(() => {
    const s = session.current;
    if (!s) return;
    for (const e of latest.current.elements) for (const [name, value] of inputsOf(e, pressed.current)) s.sim.setInput(name, value);
  }, []);

  const show = useCallback(() => {
    const s = session.current, c = circuit.current;
    if (!s || !c) return;
    const { sim } = s;
    const voltages: Record<string, number> = {};
    for (const node of Object.keys(c.program.nodes)) voltages[node] = sim.node(node);
    const scale = Math.max(1, ...Object.values(voltages).map(Math.abs));
    const leds: Record<string, number> = {};
    const results: Record<string, ElementResult> = {};
    for (const [id, quantities] of Object.entries(c.program.parts)) {
      const kind = c.program.kinds[id];
      const current = quantities.I ?? quantities.I_C ?? quantities.I_5V;
      const voltage = quantities.U ?? quantities.U_BE;
      const I = current === undefined ? null : sim.x[current];
      if (kind === "LED" && I !== null) {
        const span = sim.t - glow.current.since;
        const mean = span > 0 && glow.current.charge.has(id) ? glow.current.charge.get(id)! / span : I;
        leds[id] = Math.min(1, Math.max(0, mean / 0.02));
      }
      results[id] = {
        value: "", solved: false,
        U: voltage === undefined ? null : si(Math.abs(sim.x[voltage]), "V"),
        I: I === null ? null : si(Math.abs(I), "A"),
        P: null,
        reversed: I !== null && I < 0,
      };
    }
    glow.current = { since: sim.t, last: sim.t, charge: new Map() };
    setFrame((f) => ({
      t: sim.t, voltages, scale, leds, results, behind: f?.behind ?? false,
      wires: c.wires.map((node) => (node === null ? null : voltages[node] ?? null)),
    }));
    setTraces(scopeRef.current.map((name) => history.current.get(name) ?? { name, t: [], v: [] }));
  }, []);

  /** Samples for the scope: at most SCOPE_POINTS over its window (the last second, at the speed chosen). */
  const record = useCallback(() => {
    const s = session.current, c = circuit.current;
    if (!s || !c) return;
    const g = glow.current, dt = s.sim.t - g.last;
    if (dt > 0) {
      for (const [id, kind] of Object.entries(c.program.kinds)) {
        const i = c.program.parts[id]?.I;
        if (kind === "LED" && i !== undefined) g.charge.set(id, (g.charge.get(id) ?? 0) + Math.max(0, s.sim.x[i]) * dt);
      }
      g.last = s.sim.t;
    }
    const window = Math.max(1e-4, speedRef.current * 2);
    for (const name of scopeRef.current) {
      let trace = history.current.get(name);
      if (!trace) history.current.set(name, (trace = { name, t: [], v: [] }));
      const last = trace.t[trace.t.length - 1];
      if (last !== undefined && s.sim.t - last < window / SCOPE_POINTS) continue;
      trace.t.push(s.sim.t);
      trace.v.push(name.startsWith("V_") && !s.sim.program.unknowns.includes(name) ? s.sim.node(name.slice(2)) : s.sim.value(name));
      while (trace.t.length && trace.t[0] < s.sim.t - window) {
        trace.t.shift();
        trace.v.shift();
      }
    }
  }, []);

  const upload = useCallback(async (id: string) => {
    const s = session.current;
    const element = latest.current.elements.find((e) => e.id === id);
    if (!s || !element) return;
    const sketch = element.text ?? "";
    setSketches((all) => ({ ...all, [id]: { kind: "compiling" } }));
    const exit = await compile({ payload: { sketch } });
    if (session.current !== s) return; // stopped meanwhile
    if (exit._tag === "Failure") {
      const e = failure(exit.cause);
      const state: SketchState = e?._tag === "CompileFailed" ? { kind: "failed", output: (e as { output: string }).output }
        : e?._tag === "CompilerUnavailable" ? { kind: "unavailable" }
        : e?._tag === "Unauthorized" ? { kind: "signedOut" }
        : { kind: "unreachable" };
      setSketches((all) => ({ ...all, [id]: state }));
      return;
    }
    const at = s.boards.findIndex((b) => b.label === id);
    if (at >= 0) s.boards.splice(at, 1); // a new sketch: the chip starts over
    s.attach(id, exit.value.hex).uno.onSerial = (c) => {
      serialText.current = (serialText.current + c).slice(-4000);
    };
    setSketches((all) => ({ ...all, [id]: { kind: "running", sketch } }));
  }, [compile]);

  const start = useCallback(async () => {
    setStatus("starting");
    setError(null);
    try {
      await kernel.ready;
      const compiled = await kernel.live(latest.current);
      if ("error" in compiled) {
        setError(compiled.error);
        setStatus("off");
        return;
      }
      circuit.current = compiled;
      session.current = new Session(compiled);
      glow.current = { since: 0, last: 0, charge: new Map() };
      built.current = structure(latest.current);
      history.current.clear();
      serialText.current = "";
      setSerial("");
      setSketches({});
      setScope((kept) => {
        const known = kept.filter((n) => compiled.program.unknowns.includes(n) || n.startsWith("V_"));
        return known.length ? known : defaultScope(compiled);
      });
      applyInputs();
      setStatus("running");
      for (const e of latest.current.elements) if (e.kind === "arduino") void upload(e.id);
    } catch (e) {
      setError({ data: String(e) });
      setStatus("off");
    }
  }, [applyInputs, upload]);

  const stop = useCallback(() => {
    session.current = null;
    circuit.current = null;
    setStatus("off");
    setFrame(null);
    setTraces([]);
  }, []);

  // the frames: as much simulated time as passed on the clock (times the speed), within the budget
  useEffect(() => {
    if (status !== "running") return;
    let raf = 0, last = performance.now(), shown = 0;
    const tick = (now: number) => {
      const s = session.current;
      if (!s) return;
      const elapsed = Math.min(0.1, (now - last) / 1000);
      last = now;
      const target = s.sim.t + elapsed * speedRef.current;
      const dtMax = Math.max(1e-7, speedRef.current * 1e-3);
      const began = performance.now();
      let behind = false;
      try {
        while (s.sim.t < target - 1e-15) {
          s.advanceTo(Math.min(target, s.sim.t + dtMax * 4), dtMax, record);
          if (performance.now() - began > FRAME_BUDGET) {
            behind = s.sim.t < target - 1e-12;
            break;
          }
        }
      } catch (e) {
        const time = e instanceof NoConvergence ? e.time : s.sim.t;
        setError(e instanceof NoConvergence
          ? { data: String(e), issue: { type: "NoConvergence", time } } : { data: String(e) });
        setStatus("paused");
        return;
      }
      if (now - shown > 33) { // the board: 30 times a second is plenty
        shown = now;
        show();
        setFrame((f) => (f ? { ...f, behind } : f));
        if (serialText.current !== serial) setSerial(serialText.current);
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, show, record]);

  // the drawing changed while running: its inputs are simply set; anything else starts it anew
  useEffect(() => {
    if (!session.current) return;
    if (structure(schematic) !== built.current) {
      void start();
      return;
    }
    applyInputs();
    if (statusRef.current === "paused") show();
  }, [schematic, start, applyInputs, show]);

  useEffect(() => () => { session.current = null; }, []);

  return {
    status, error, frame, speed, setSpeed, traces, scope, serial, sketches,
    start,
    stop,
    pause: () => setStatus((s) => (s === "running" ? "paused" : s)),
    resume: () => { setError(null); setStatus((s) => (s === "paused" ? "running" : s)); },
    /** A button held down (or let go). */
    press: (id: string, down: boolean) => {
      if (down) pressed.current.add(id);
      else pressed.current.delete(id);
      applyInputs();
    },
    setScope: (names: string[]) => {
      setScope(names);
      scopeRef.current = names;
      if (session.current) show();
    },
    /** Every quantity the scope can show: node voltages, then elements' voltages and currents. */
    quantities: (): string[] => {
      const c = circuit.current;
      if (!c) return [];
      const nodes = Object.keys(c.program.nodes).filter((n) => n !== "GND").map((n) => `V_${n}`);
      const parts = Object.entries(c.program.parts).flatMap(([, q]) =>
        Object.values(q).map((i) => c.program.unknowns[i]));
      return [...nodes, ...parts.filter((n) => !nodes.includes(n))];
    },
    upload,
    clearSerial: () => { serialText.current = ""; setSerial(""); },
    /** Text typed into the serial monitor: to every Arduino's Serial.read(). */
    sendSerial: (text: string) => { for (const board of session.current?.boards ?? []) board.uno.send(text); },
  };
}

export type Live = ReturnType<typeof useLive>;
