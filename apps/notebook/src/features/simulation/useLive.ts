// A schematic cell running in time: its circuit compiled once (Python: kernel.live), then stepped
// in the page as the frames go by (engine.ts), with the Arduinos in it running their sketches
// (session.ts). What the board draws — the wires' voltages, the LEDs' and segments' glow, a servo's
// angle, the readings — is taken from it every frame, and the buzzers are heard (sound.ts);
// switches, buttons, potentiometers and the sensors' light and temperature set its inputs while it runs.
import { useAtomSet } from "@effect-atom/atom-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { failure } from "@/features/notes/sync";
import { kernel } from "@/features/python";
import type { ElementData, ElementResult, SchematicData } from "@/shared/model/types";
import type { Failure } from "@/shared/model/issues";
import { compileSketch } from "./atoms";
import { compiler } from "./compiler";
import { NoConvergence, type LiveCircuit } from "./engine";
import { si } from "./format";
import { lcd, screen, watch as read, type Lcd, type Screen } from "./lcd";
import { buzzing, heard, listen, ping, servoing, sonar, turn, watch, type Buzzing, type Servoing, type Sonar } from "./peripherals";
import { Session } from "./session";
import { Sound, wake } from "./sound";

export type LiveStatus = "off" | "starting" | "running" | "paused";

/** What the board shows of the circuit at one moment. */
export interface LiveFrame {
  t: number;
  voltages: Record<string, number>; // node → V
  wires: (number | null)[]; // each wire's voltage (null: on no node)
  pins: Record<string, (number | null)[]>; // each element's pins' voltages (null: on no node)
  scale: number; // the largest |V| on the board, for the wires' colours
  leds: Record<string, number>; // LED id → brightness 0–1
  // what else an element shows, as CSS variables of its symbol: an RGB LED's and a display's glow per
  // channel (r, a, dp, …: 0–1), a servo's angle (degrees), a buzzer sounding (sound: 0 or 1)
  looks: Record<string, Record<string, number>>;
  screens: Record<string, Screen>; // each LCD: what it shows
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
  | { kind: "running"; sketch: string; where: "page" | "server" } // where it was compiled
  | { kind: "failed"; output: string }
  | { kind: "tooBig"; size: number; flash: number }
  | { kind: "unavailable" | "signedOut" | "unreachable" };

const FRAME_BUDGET = 12; // ms of computing per frame at most, for all of them (else the simulation falls behind)
let runningNow = 0; // circuits running on the page: they share the frame's budget
const SCOPE_POINTS = 600;
export const SPEEDS = [1, 0.1, 0.01, 0.001];

// electro.devices: what glows (each LED's channels: its current's name, "" for I)
const LIGHTS: Record<string, string[]> = {
  LED: [""], RGBLED: ["r", "g", "b"], SevenSegment: ["a", "b", "c", "d", "e", "f", "g", "dp"],
};
const LCD_DATA = ["d0", "d1", "d2", "d3", "d4", "d5", "d6", "d7"];
const LED_RATED = 0.02; // A: full brightness

/** The drawing without what may change while it runs (switches, positions, sketches): if that
 *  is the same, the circuit is too. */
function structure(sch: SchematicData): string {
  const inputs = new Set(["switch", "button", "potentiometer", "photoresistor", "thermistor", "ultrasonic", "arduino"]);
  return JSON.stringify({ ...sch, elements: sch.elements.map((e) => (inputs.has(e.kind) ? { ...e, text: null } : e)) });
}

/** The inputs an element sets: [input name, value]. */
function inputsOf(e: ElementData, pressed: Set<string>): [string, number][] {
  if (e.kind === "switch") return [[`${e.id}_closed`, e.text === "closed" ? 1 : 0]];
  if (e.kind === "button") return [[`${e.id}_closed`, pressed.has(e.id) ? 1 : 0]];
  if (e.kind === "potentiometer") return [[`${e.id}_position`, Number(e.text ?? 0.5)]];
  if (e.kind === "photoresistor") return [[`${e.id}_lux`, Math.max(0.1, Number(e.text ?? 100) || 100)]];
  if (e.kind === "thermistor") return [[`${e.id}_temperature`, Number(e.text ?? 25) || 0]];
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
  const [probeTraces, setProbeTraces] = useState<ScopeTrace[]>([]); // what the meter shows (an element's, a wire's)
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
  const probeRef = useRef<string[]>([]); // the quantities the meter is on
  // everything recorded: the scope's quantities and the meter's (worked out again only when either changes:
  // record() runs after every step)
  const recording = useRef({ scope: [] as string[], probe: [] as string[], names: [] as string[] });
  const recorded = () => {
    const r = recording.current;
    if (r.scope !== scopeRef.current || r.probe !== probeRef.current)
      recording.current = { scope: scopeRef.current, probe: probeRef.current, names: [...new Set([...scopeRef.current, ...probeRef.current])] };
    return recording.current.names;
  };
  const lights = useRef<[string, string, number][]>([]); // each LED's id, channel ("" for a plain one), its current's index in x
  const buzzers = useRef<Buzzing[]>([]);
  const servos = useRef<Servoing[]>([]);
  const lcds = useRef<Lcd[]>([]);
  const sonars = useRef<Sonar[]>([]);
  const sound = useRef(new Sound());
  const [muted, setMuted] = useState(false);
  const mutedRef = useRef(muted);
  mutedRef.current = muted;
  const [hasSound, setHasSound] = useState(false); // a buzzer in it: the bar offers to mute
  const history = useRef(new Map<string, ScopeTrace>());
  const serialText = useRef("");
  const statusRef = useRef(status);
  statusRef.current = status;
  // each LED channel's charge since the board was last drawn (id:channel): its glow is the average current, so PWM dims it
  const glow = useRef({ since: 0, last: 0, charge: new Map<string, number>() });

  const applyInputs = useCallback(() => {
    const s = session.current;
    if (!s) return;
    for (const e of latest.current.elements) for (const [name, value] of inputsOf(e, pressed.current)) s.sim.setInput(name, value);
  }, []);

  /** The board as the circuit is now; `behind`: whether the last frame kept up (else as it was). */
  const show = useCallback((behind?: boolean) => {
    const s = session.current, c = circuit.current;
    if (!s || !c) return;
    const { sim } = s;
    const voltages: Record<string, number> = {};
    for (const node of Object.keys(c.program.nodes)) voltages[node] = sim.node(node);
    const scale = Math.max(1, ...Object.values(voltages).map(Math.abs));
    const leds: Record<string, number> = {};
    const looks: Record<string, Record<string, number>> = {};
    const span = sim.t - glow.current.since;
    for (const [id, channel, i] of lights.current) {
      const key = `${id}:${channel}`;
      const mean = span > 0 && glow.current.charge.has(key) ? glow.current.charge.get(key)! / span : sim.x[i];
      const bright = Math.min(1, Math.max(0, mean / LED_RATED));
      if (channel) (looks[id] ??= {})[channel] = bright;
      else leds[id] = bright;
    }
    const audible = statusRef.current === "running" && !mutedRef.current;
    for (const b of buzzers.current) {
      if (span <= 0) continue; // nothing has happened since: it sounds as it did
      const { frequency, volume } = heard(b, span);
      (looks[b.id] ??= {}).sound = frequency === null ? 0 : 1;
      // time running slower lowers the tone as much
      if (audible) sound.current.set(b.id, frequency === null ? null : frequency * speedRef.current, volume);
    }
    for (const m of servos.current) (looks[m.id] ??= {}).angle = turn(m, sim.t);
    for (const u of sonars.current) (looks[u.id] ??= {}).ping = sim.t < u.until ? 1 : 0;
    const screens: Record<string, Screen> = {};
    for (const d of lcds.current) screens[d.id] = screen(d, sim.x);
    const results: Record<string, ElementResult> = {};
    for (const [id, quantities] of Object.entries(c.program.parts)) {
      const current = quantities.I ?? quantities.I_C ?? quantities.I_D ?? quantities.I_5V;
      const voltage = quantities.U ?? quantities.U_BE ?? quantities.U_GS;
      const I = current === undefined ? null : sim.x[current];
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
      t: sim.t, voltages, scale, leds, looks, screens, results, behind: behind ?? f?.behind ?? false,
      wires: c.wires.map((node) => (node === null ? null : voltages[node] ?? null)),
      pins: Object.fromEntries(Object.entries(c.pins).map(([id, nodes]) =>
        [id, nodes.map((node) => (node === null ? null : voltages[node] ?? null))])),
    }));
    setTraces(scopeRef.current.map((name) => history.current.get(name) ?? { name, t: [], v: [] }));
    setProbeTraces(probeRef.current.map((name) => history.current.get(name) ?? { name, t: [], v: [] }));
  }, []);

  /** Samples for the scope: at most SCOPE_POINTS over its window (the last second, at the speed chosen). */
  const record = useCallback(() => {
    const s = session.current, c = circuit.current;
    if (!s || !c) return;
    const g = glow.current, dt = s.sim.t - g.last;
    if (dt > 0) {
      for (const [id, channel, i] of lights.current) {
        const key = `${id}:${channel}`;
        g.charge.set(key, (g.charge.get(key) ?? 0) + Math.max(0, s.sim.x[i]) * dt);
      }
      for (const b of buzzers.current) listen(b, s.sim.x[b.u], dt);
      g.last = s.sim.t;
    }
    for (const m of servos.current) watch(m, s.sim.x[m.u], s.sim.t);
    for (const d of lcds.current) read(d, s.sim.x);
    for (const u of sonars.current) {
      // (the distance is looked up only while the trigger is high: a ping is sent as it falls)
      const distance = u.high ? Number(latest.current.elements.find((e) => e.id === u.id)?.text ?? 100) || 100 : 0;
      const echo = ping(u, s.sim.x[u.trig], s.sim.t, distance);
      if (!echo) continue;
      const [at, length] = echo, input = `${u.id}_echo`;
      s.schedule(at, () => s.sim.setInput(input, 1));
      s.schedule(at + length, () => s.sim.setInput(input, 0));
    }
    const window = Math.max(1e-4, speedRef.current * 2);
    for (const name of recorded()) {
      let trace = history.current.get(name);
      if (!trace) history.current.set(name, (trace = { name, t: [], v: [] }));
      const last = trace.t[trace.t.length - 1];
      if (last !== undefined && s.sim.t - last < window / SCOPE_POINTS) continue;
      trace.t.push(s.sim.t);
      trace.v.push(s.sim.at(name));
      let old = 0;
      while (old < trace.t.length && trace.t[old] < s.sim.t - window) old++;
      if (old) {
        trace.t.splice(0, old);
        trace.v.splice(0, old);
      }
    }
  }, []);

  const upload = useCallback(async (id: string) => {
    const s = session.current;
    const element = latest.current.elements.find((e) => e.id === id);
    if (!s || !element) return;
    const sketch = element.text ?? "";
    setSketches((all) => ({ ...all, [id]: { kind: "compiling" } }));
    const run = (hex: string, where: "page" | "server") => {
      const at = s.boards.findIndex((b) => b.label === id);
      if (at >= 0) s.boards.splice(at, 1); // a new sketch: the chip starts over
      s.attach(id, hex).uno.onSerial = (c) => {
        serialText.current = (serialText.current + c).slice(-4000);
      };
      setSketches((all) => ({ ...all, [id]: { kind: "running", sketch, where } }));
    };
    // in the page first; the server only if the page's compiler could not be loaded
    const local = await compiler.compile(sketch).catch(() => null);
    if (session.current !== s) return; // stopped meanwhile
    if (local) {
      if ("hex" in local) run(local.hex, "page");
      else setSketches((all) => ({
        ...all, [id]: "failed" in local ? { kind: "failed", output: local.failed } : { kind: "tooBig", size: local.tooBig, flash: local.flash },
      }));
      return;
    }
    const exit = await compile({ payload: { sketch } });
    if (session.current !== s) return;
    if (exit._tag === "Failure") {
      const e = failure(exit.cause);
      const state: SketchState = e?._tag === "CompileFailed" ? { kind: "failed", output: (e as { output: string }).output }
        : e?._tag === "CompilerUnavailable" ? { kind: "unavailable" }
        : e?._tag === "Unauthorized" ? { kind: "signedOut" }
        : { kind: "unreachable" };
      setSketches((all) => ({ ...all, [id]: state }));
      return;
    }
    run(exit.value.hex, "server");
  }, [compile]);

  /** Run the drawing (or `drawing`: one just made from the code view, not on the board yet). */
  const start = useCallback(async (drawing?: SchematicData) => {
    if (drawing) latest.current = drawing;
    wake(); // (still the click that started it: the page may make sounds)
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
      const { kinds, parts } = compiled.program;
      lights.current = Object.entries(kinds).flatMap(([id, kind]) => (LIGHTS[kind] ?? []).flatMap((channel) => {
        const i = parts[id]?.[channel ? `I_${channel}` : "I"];
        return i === undefined ? [] : [[id, channel, i] as [string, string, number]];
      }));
      sound.current.close();
      buzzers.current = Object.entries(kinds).flatMap(([id, kind]) =>
        (kind === "Buzzer" || kind === "PassiveBuzzer") && parts[id]?.U !== undefined
          ? [buzzing(id, parts[id].U, kind === "Buzzer")] : []);
      servos.current = Object.entries(kinds).flatMap(([id, kind]) =>
        kind === "Servo" && parts[id]?.U_sig !== undefined
          ? [servoing(id, parts[id].U_sig)] : []);
      lcds.current = Object.entries(kinds).flatMap(([id, kind]) => {
        const q = parts[id];
        return kind === "LCD1602" && q ? [lcd(id, {
          power: q.U, contrast: q.U_v0, backlight: q.I_a, rs: q.U_rs, rw: q.U_rw, e: q.U_e, data: LCD_DATA.map((d) => q[`U_${d}`]),
        })] : [];
      });
      sonars.current = Object.entries(kinds).flatMap(([id, kind]) =>
        kind === "Ultrasonic" && parts[id]?.U_trig !== undefined ? [sonar(id, parts[id].U_trig)] : []);
      setHasSound(buzzers.current.length > 0);
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
    sound.current.close();
    session.current = null;
    circuit.current = null;
    setStatus("off");
    setFrame(null);
    setTraces([]);
    setProbeTraces([]);
    probeRef.current = [];
  }, []);

  // the frames: as much simulated time as passed on the clock (times the speed), within the budget
  useEffect(() => {
    if (status !== "running") return;
    let raf = 0, last = performance.now(), shown = 0;
    runningNow++;
    const tick = (now: number) => {
      const s = session.current;
      if (!s) return;
      const elapsed = Math.min(0.1, (now - last) / 1000);
      last = now;
      const target = s.sim.t + elapsed * speedRef.current;
      const dtMax = Math.max(1e-7, speedRef.current * 1e-3);
      const began = performance.now(), budget = FRAME_BUDGET / Math.max(1, runningNow);
      let behind = false;
      try {
        while (s.sim.t < target - 1e-15) {
          s.advanceTo(Math.min(target, s.sim.t + dtMax * 4), dtMax, record);
          if (performance.now() - began > budget) {
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
      // the board: 30 times a second is plenty, and not at all while it is off screen (it keeps
      // running and recording; it is drawn as it is the moment it comes back)
      if (now - shown > 33 && onScreen.current) {
        shown = now;
        show(behind);
        setSerial(serialText.current); // (the same text: no render)
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(raf);
      runningNow--;
    };
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

  useEffect(() => () => { session.current = null; sound.current.close(); }, []);

  // paused or muted: quiet at once (running again, the next drawing sets them)
  useEffect(() => {
    if (status !== "running" || muted) sound.current.silence();
  }, [status, muted]);

  const onScreen = useRef(true);
  /** Whether the board can be seen (scrolled out of view: nothing is drawn). */
  const setOnScreen = useCallback((seen: boolean) => {
    const back = seen && !onScreen.current;
    onScreen.current = seen;
    if (back && session.current) {
      show();
      setSerial(serialText.current);
    }
  }, [show]);

  return {
    status, error, frame, speed, setSpeed, traces, scope, serial, sketches,
    start,
    stop,
    pause: () => setStatus((s) => (s === "running" ? "paused" : s)),
    resume: () => { wake(); setError(null); setStatus((s) => (s === "paused" ? "running" : s)); },
    /** A buzzer in the circuit (the bar offers to mute it); muted, whether it is. */
    hasSound,
    muted,
    setMuted: (quiet: boolean) => { if (!quiet) wake(); setMuted(quiet); },
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
    /** The meter on these quantities (none: off); their samples in probeTraces. */
    setProbe: (names: string[]) => {
      probeRef.current = names;
      if (session.current) show();
    },
    probeTraces,
    /** An element's quantities (U, I, …) as the scope names them. */
    quantitiesOf: (id: string): string[] => {
      const c = circuit.current;
      const parts = c?.program.parts[id];
      return c && parts ? Object.values(parts).map((i) => c.program.unknowns[i]) : [];
    },
    /** The node a wire is on, as the scope names its voltage (V_…); null: on none. */
    wireVoltage: (index: number): string | null => {
      const node = circuit.current?.wires[index];
      return node && node !== "GND" ? `V_${node}` : null;
    },
    quantities: (): string[] => {
      const c = circuit.current;
      if (!c) return [];
      const nodes = Object.keys(c.program.nodes).filter((n) => n !== "GND").map((n) => `V_${n}`);
      const parts = Object.entries(c.program.parts).flatMap(([, q]) =>
        Object.values(q).map((i) => c.program.unknowns[i]));
      return [...nodes, ...parts.filter((n) => !nodes.includes(n))];
    },
    upload,
    setOnScreen,
    /** The error shown under the board, away (it comes back if it happens again). */
    dismissError: () => setError(null),
    clearSerial: () => { serialText.current = ""; setSerial(""); },
    /** Text typed into the serial monitor: to every Arduino's Serial.read(). */
    sendSerial: (text: string) => { for (const board of session.current?.boards ?? []) board.uno.send(text); },
  };
}

export type Live = ReturnType<typeof useLive>;
