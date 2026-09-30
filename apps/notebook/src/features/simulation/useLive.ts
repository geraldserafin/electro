// A schematic cell running in time: its circuit compiled once (Python: kernel.live), then stepped in
// a worker (sim.worker.ts: runner.ts with the Arduinos' chips, off the page's thread), which sends
// what the board shows about 30 times a second — the wires' voltages, the LEDs' and segments' glow, a
// servo's angle, the displays, the readings, the scope. Here: the sketches compiled, the buzzers
// heard (sound.ts: Web Audio is the page's), and what the drawing changes sent on (switches, buttons,
// sliders, sensors' readings).
import { useAtomSet } from "@effect-atom/atom-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { failure } from "@/features/notes/sync";
import { kernel } from "@/features/python";
import type { ElementResult, SchematicData } from "@/shared/model/types";
import type { Failure } from "@/shared/model/issues";
import { compileSketch } from "./atoms";
import { compiler } from "./compiler";
import type { LiveCircuit } from "./engine";
import type { Firmware, Frame, OledData, Part, ScopeTrace } from "./runner";
import type { TftData } from "./tft";
import { fetchFirmware, firmwareFile } from "./firmware";
import type { Reply, Request } from "./sim.worker";
import { Sound, wake } from "./sound";
import type { Screen } from "./lcd";

export type { ScopeTrace };
export type LiveStatus = "off" | "starting" | "running" | "paused";

/** What the board shows of the circuit at one moment. */
export interface LiveFrame {
  t: number;
  voltages: Record<string, number>; // node → V
  wires: (number | null)[]; // each wire's voltage (null: on no node)
  pins: Record<string, (number | null)[]>; // each element's pins' voltages (null: on no node)
  scale: number; // the largest |V| on the board, for the wires' colours
  leds: Record<string, number>; // LED id → brightness 0–1
  looks: Record<string, Record<string, number>>; // runner.ts: Frame.looks
  screens: Record<string, Screen>; // each LCD (parallel or on I²C)
  oleds: Record<string, OledData>; // each OLED
  tfts: Record<string, TftData>; // each colour TFT (a picture only when it changed)
  results: Record<string, ElementResult>; // readings next to the elements
  behind: boolean; // the simulation cannot keep up: time runs slower than asked
}

/** An Arduino's sketch as it goes to the chip: compiling, running, or what the compiler said. */
export type SketchState =
  | { kind: "compiling" }
  | { kind: "running"; sketch: string; where: "page" | "server" | "file" } // where it was compiled (a file: given whole)
  | { kind: "failed"; output: string }
  | { kind: "tooBig"; size: number; flash: number }
  | { kind: "unavailable" | "signedOut" | "unreachable" };

export const SPEEDS = [1, 0.1, 0.01, 0.001];

/** A Pico's flash image as the server sends it (base64) → bytes. (Here, not in pico.ts: the emulator
 *  itself — rp2040js, the boot ROM — is the worker's alone.) */
const flashImage = (base64: string) => Uint8Array.from(atob(base64), (c) => c.charCodeAt(0));

/** The drawing without what may change while it runs (switches, positions, readings, sketches): if
 *  that is the same, the circuit is too. */
function structure(sch: SchematicData): string {
  const inputs = new Set(["switch", "button", "potentiometer", "photoresistor", "thermistor", "ultrasonic", "lcd1602_i2c", "arduino", "pico"]);
  return JSON.stringify({ ...sch, elements: sch.elements.map((e) => (inputs.has(e.kind) ? { ...e, text: null } : e)) });
}

const partsOf = (sch: SchematicData): Part[] => sch.elements.map(({ id, kind, text }) => ({ id, kind, text }));

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
  const [speed, setSpeedState] = useState(1);
  const [scope, setScopeState] = useState<string[]>([]);
  const [traces, setTraces] = useState<ScopeTrace[]>([]);
  const [probeTraces, setProbeTraces] = useState<ScopeTrace[]>([]); // what the meter shows (an element's, a wire's)
  const [serial, setSerial] = useState("");
  const [sketches, setSketches] = useState<Record<string, SketchState>>({});
  const [muted, setMuted] = useState(false);
  const [hasSound, setHasSound] = useState(false); // a buzzer in it: the bar offers to mute
  const compile = useAtomSet(compileSketch, { mode: "promiseExit" });

  const worker = useRef<Worker | null>(null);
  const circuit = useRef<LiveCircuit | null>(null);
  const built = useRef(""); // structure() of the drawing the worker runs
  const pressed = useRef(new Set<string>());
  const latest = useRef(schematic);
  latest.current = schematic;
  const speedRef = useRef(speed);
  speedRef.current = speed;
  const scopeRef = useRef(scope);
  scopeRef.current = scope;
  const probeRef = useRef<string[]>([]); // the quantities the meter is on
  const mutedRef = useRef(muted);
  mutedRef.current = muted;
  const statusRef = useRef(status);
  statusRef.current = status;
  const sound = useRef(new Sound());
  const serialText = useRef("");

  const tell = (request: Request) => worker.current?.postMessage(request);

  /** A frame from the worker, onto the board (and into the speakers). */
  const received = useCallback((f: Frame, behind: boolean) => {
    const c = circuit.current;
    if (!c) return;
    const { voltages } = f;
    const on = (node: string | null) => (node === null ? null : voltages[node] ?? null);
    setFrame({
      t: f.t, voltages, leds: f.leds, looks: f.looks, screens: f.screens, oleds: f.oleds, tfts: f.tfts, results: f.results, behind,
      scale: Math.max(1, ...Object.values(voltages).map(Math.abs)),
      wires: c.wires.map(on),
      pins: Object.fromEntries(Object.entries(c.pins).map(([id, nodes]) => [id, nodes.map(on)])),
    });
    const scoped = scopeRef.current.length;
    setTraces(f.traces.slice(0, scoped));
    setProbeTraces(f.traces.slice(scoped));
    if (f.serial) {
      serialText.current = (serialText.current + f.serial).slice(-4000);
      setSerial(serialText.current);
    }
    if (statusRef.current === "running" && !mutedRef.current) // time running slower lowers the tone as much
      for (const s of f.sounds) sound.current.set(s.id, s.frequency === null ? null : s.frequency * speedRef.current, s.volume);
  }, []);

  const upload = useCallback(async (id: string) => {
    const w = worker.current;
    const element = latest.current.elements.find((e) => e.id === id);
    if (!w || !element) return;
    const sketch = element.text ?? "";
    const board = element.kind === "pico" ? "pico" : "uno";
    setSketches((all) => ({ ...all, [id]: { kind: "compiling" } }));
    const run = (firmware: Firmware, where: "page" | "server" | "file") => {
      w.postMessage({ type: "attach", id, firmware } satisfies Request);
      setSketches((all) => ({ ...all, [id]: { kind: "running", sketch, where } }));
    };
    // a Pico's program given whole: the file its text names
    const file = board === "pico" ? firmwareFile(sketch) : null;
    if (file) {
      const image = await fetchFirmware(file).catch((e: unknown) => String(e instanceof Error ? e.message : e));
      if (worker.current !== w) return;
      if (typeof image === "string") setSketches((all) => ({ ...all, [id]: { kind: "failed", output: image } }));
      else run({ board: "pico", image }, "file");
      return;
    }
    // an Uno's in the page first, the server only if the page's compiler could not be loaded; a Pico's
    // on the server (the page's compiler is AVR's)
    const local = board === "uno" ? await compiler.compile(sketch).catch(() => null) : null;
    if (worker.current !== w) return; // stopped meanwhile
    if (local) {
      if ("hex" in local) run({ board: "uno", hex: local.hex }, "page");
      else setSketches((all) => ({
        ...all, [id]: "failed" in local ? { kind: "failed", output: local.failed } : { kind: "tooBig", size: local.tooBig, flash: local.flash },
      }));
      return;
    }
    const exit = await compile({ payload: { sketch, board } });
    if (worker.current !== w) return;
    if (exit._tag === "Failure") {
      const e = failure(exit.cause);
      const state: SketchState = e?._tag === "CompileFailed" ? { kind: "failed", output: (e as { output: string }).output }
        : e?._tag === "CompilerUnavailable" ? { kind: "unavailable" }
        : e?._tag === "Unauthorized" ? { kind: "signedOut" }
        : { kind: "unreachable" };
      setSketches((all) => ({ ...all, [id]: state }));
      return;
    }
    const compiled = exit.value;
    run("image" in compiled ? { board: "pico", image: flashImage(compiled.image) } : { board: "uno", hex: compiled.hex }, "server");
  }, [compile]);

  const halt = () => {
    worker.current?.terminate();
    worker.current = null;
    sound.current.close();
  };

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
      halt();
      circuit.current = compiled;
      built.current = structure(latest.current);
      const w = new Worker(new URL("./sim.worker.ts", import.meta.url), { type: "module" });
      worker.current = w;
      w.onmessage = (event: MessageEvent<Reply>) => {
        if (worker.current !== w) return;
        const r = event.data;
        if (r.type === "frame") received(r.frame, r.behind);
        else {
          setError(r.message.includes("NoConvergence") && r.time !== null
            ? { data: r.message, issue: { type: "NoConvergence", time: r.time } } : { data: r.message });
          setStatus("paused");
        }
      };
      const { kinds } = compiled.program;
      setHasSound(Object.values(kinds).some((k) => k === "Buzzer" || k === "PassiveBuzzer"));
      serialText.current = "";
      setSerial("");
      setSketches({});
      const known = scopeRef.current.filter((n) => compiled.program.unknowns.includes(n) || n.startsWith("V_"));
      const first = known.length ? known : defaultScope(compiled);
      scopeRef.current = first;
      setScopeState(first);
      w.postMessage({
        type: "start", circuit: compiled, parts: partsOf(latest.current), pressed: [...pressed.current],
        speed: speedRef.current, scope: first, probe: probeRef.current,
      } satisfies Request);
      setStatus("running");
      for (const e of latest.current.elements) if (e.kind === "arduino" || e.kind === "pico") void upload(e.id);
    } catch (e) {
      setError({ data: String(e) });
      setStatus("off");
    }
  }, [received, upload]);

  const stop = useCallback(() => {
    halt();
    circuit.current = null;
    setStatus("off");
    setFrame(null);
    setTraces([]);
    setProbeTraces([]);
    probeRef.current = [];
  }, []);

  // the drawing changed while running: what it sets is sent on; anything else starts it anew
  useEffect(() => {
    if (!worker.current) return;
    if (structure(schematic) !== built.current) {
      void start();
      return;
    }
    tell({ type: "parts", parts: partsOf(schematic), pressed: [...pressed.current] });
  }, [schematic, start]);

  useEffect(() => () => halt(), []);

  // paused or muted: quiet at once (going on, the next frame sets them)
  useEffect(() => {
    if (status !== "running" || muted) sound.current.silence();
  }, [status, muted]);

  const watch = (scopeNames: string[], probe: string[]) => tell({ type: "watch", scope: scopeNames, probe });

  return {
    status, error, frame, speed, traces, scope, serial, sketches,
    start,
    stop,
    setSpeed: (value: number) => { setSpeedState(value); tell({ type: "speed", speed: value }); },
    pause: () => { tell({ type: "run", running: false }); setStatus((s) => (s === "running" ? "paused" : s)); },
    resume: () => { wake(); setError(null); tell({ type: "run", running: true }); setStatus((s) => (s === "paused" ? "running" : s)); },
    /** A buzzer in the circuit (the bar offers to mute it); muted, whether it is. */
    hasSound,
    muted,
    setMuted: (quiet: boolean) => { if (!quiet) wake(); setMuted(quiet); },
    /** A button held down (or let go). */
    press: (id: string, down: boolean) => {
      if (down) pressed.current.add(id);
      else pressed.current.delete(id);
      tell({ type: "parts", parts: partsOf(latest.current), pressed: [...pressed.current] });
    },
    setScope: (names: string[]) => {
      setScopeState(names);
      scopeRef.current = names;
      watch(names, probeRef.current);
    },
    /** The meter on these quantities (none: off); their samples in probeTraces. */
    setProbe: (names: string[]) => {
      probeRef.current = names;
      watch(scopeRef.current, names);
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
    /** Every quantity the scope can show: node voltages, then elements' voltages and currents. */
    quantities: (): string[] => {
      const c = circuit.current;
      if (!c) return [];
      const nodes = Object.keys(c.program.nodes).filter((n) => n !== "GND").map((n) => `V_${n}`);
      const parts = Object.entries(c.program.parts).flatMap(([, q]) => Object.values(q).map((i) => c.program.unknowns[i]));
      return [...nodes, ...parts.filter((n) => !nodes.includes(n))];
    },
    upload,
    /** Whether the board can be seen (scrolled out of view: it runs, but nothing is sent to draw). */
    setOnScreen: useCallback((seen: boolean) => tell({ type: "visible", visible: seen }), []),
    /** The error shown under the board, away (it comes back if it happens again). */
    dismissError: () => setError(null),
    clearSerial: () => { serialText.current = ""; setSerial(""); },
    /** Text typed into the serial monitor: to every Arduino's Serial.read(). */
    sendSerial: (text: string) => tell({ type: "send", text }),
  };
}

export type Live = ReturnType<typeof useLive>;
