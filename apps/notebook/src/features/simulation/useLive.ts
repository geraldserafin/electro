// A schematic cell running in time: its circuit compiled once (Python: kernel.live), then stepped in
// a worker (sim.worker.ts: runner.ts with the Arduinos' chips, off the page's thread), which sends
// what the board shows about 30 times a second — the wires' voltages, the LEDs' and segments' glow, a
// servo's angle, the displays, the readings, the scope. Here: the sketches compiled, the buzzers
// heard (sound.ts: Web Audio is the page's), and what the drawing changes sent on (switches, buttons,
// sliders, sensors' readings).
import { useCallback, useEffect, useRef, useState } from "react";
import { kernel } from "@/features/python";
import type { Failure } from "@/shared/model/issues";
import type { ElementResult, SchematicData } from "@/shared/model/types";
import { compiler } from "./compiler";
import { prebuilt } from "./compiler/prebuilt";
import type { LiveCircuit } from "./engine";
import { fetchFirmware, firmwareFile } from "./firmware";
import type { Screen } from "./lcd";
import type { Firmware, Frame, OledData, Part, ScopeTrace } from "./runner";
import type { Reply, Request } from "./sim.worker";
import { Sound, wake } from "./sound";
import type { TftData } from "./tft";

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
  tfts: Record<string, TftData & { pictures: Pictures }>; // each colour TFT, how lit, and where its pictures come from
  results: Record<string, ElementResult>; // readings next to the elements
  behind: boolean; // the simulation cannot keep up: time runs slower than asked
}

/** An Arduino's sketch as it goes to the chip: compiling, running, or what the compiler said. */
export type SketchState =
  | { kind: "compiling" }
  | { kind: "running"; sketch: string; where: "page" | "file" } // compiled in the page, or a file given whole
  | { kind: "failed"; output: string }
  | { kind: "tooBig"; size: number; flash: number }
  | { kind: "unavailable" }; // the compiler could not be fetched

export const SPEEDS = [1, 0.1, 0.01, 0.001];

/** The TFTs' pictures as the worker sends them (apart from the frames): each drawn at once where it is watched. */
class Pictures {
  private last = new Map<string, Uint8ClampedArray>();
  private drawers = new Map<string, (image: Uint8ClampedArray) => void>();

  put(id: string, image: Uint8ClampedArray) {
    this.last.set(id, image);
    this.drawers.get(id)?.(image);
  }

  watch(id: string, draw: (image: Uint8ClampedArray) => void) {
    this.drawers.set(id, draw);
    const last = this.last.get(id);
    if (last) draw(last);
    return () => {
      if (this.drawers.get(id) === draw) this.drawers.delete(id);
    };
  }

  clear() {
    this.last.clear();
  }
}

/** The drawing without what may change while it runs (switches, positions, readings, sketches): if
 *  that is the same, the circuit is too. */
function structure(sch: SchematicData): string {
  const inputs = new Set([
    "switch",
    "button",
    "potentiometer",
    "photoresistor",
    "thermistor",
    "ultrasonic",
    "lcd1602_i2c",
    "arduino",
    "pico",
  ]);
  return JSON.stringify({ ...sch, elements: sch.elements.map((e) => (inputs.has(e.kind) ? { ...e, text: null } : e)) });
}

const partsOf = (sch: SchematicData): Part[] => sch.elements.map(({ id, kind, text }) => ({ id, kind, text }));

/** The scope's quantities to start with: LEDs' currents, capacitors' voltages (at most four). */
function defaultScope(circuit: LiveCircuit): string[] {
  const { kinds, unknowns } = circuit.program;
  const leds = Object.keys(kinds)
    .filter((k) => kinds[k] === "LED")
    .map((k) => `I_${k}`);
  const caps = Object.keys(kinds)
    .filter((k) => kinds[k] === "Capacitor")
    .map((k) => `U_${k}`);
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
  const pictures = useRef(new Pictures());

  const tell = (request: Request) => worker.current?.postMessage(request);

  /** A frame from the worker, onto the board (and into the speakers). */
  const received = useCallback((f: Frame, behind: boolean) => {
    const c = circuit.current;
    if (!c) return;
    const { voltages } = f;
    const on = (node: string | null) => (node === null ? null : (voltages[node] ?? null));
    setFrame({
      t: f.t,
      voltages,
      leds: f.leds,
      looks: f.looks,
      screens: f.screens,
      oleds: f.oleds,
      results: f.results,
      behind,
      tfts: Object.fromEntries(Object.entries(f.tfts).map(([id, d]) => [id, { ...d, pictures: pictures.current }])),
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
    if (statusRef.current === "running" && !mutedRef.current)
      // time running slower lowers the tone as much
      for (const s of f.sounds)
        sound.current.set(s.id, s.frequency === null ? null : s.frequency * speedRef.current, s.volume);
  }, []);

  const upload = useCallback(async (id: string) => {
    const w = worker.current;
    const element = latest.current.elements.find((e) => e.id === id);
    if (!w || !element) return;
    const sketch = element.text ?? "";
    const board = element.kind === "pico" ? "pico" : "uno";
    setSketches((all) => ({ ...all, [id]: { kind: "compiling" } }));
    const run = (firmware: Firmware, where: "page" | "file") => {
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
    // an example's, as it is there: compiled ahead
    const ahead = await prebuilt(board, sketch).catch(() => null);
    if (worker.current !== w) return;
    if (ahead) return run(ahead, "page");
    // compiled in the page (compiler/): the compiler fetched the first time, each board's parts too
    const compiled = await compiler.compile(sketch, board).catch(() => null);
    if (worker.current !== w) return; // stopped meanwhile
    if (compiled && "hex" in compiled) return run({ board: "uno", hex: compiled.hex }, "page");
    if (compiled && "image" in compiled) return run({ board: "pico", image: compiled.image }, "page");
    const state: SketchState = !compiled
      ? { kind: "unavailable" }
      : "failed" in compiled
        ? { kind: "failed", output: compiled.failed }
        : { kind: "tooBig", size: compiled.tooBig, flash: compiled.flash };
    setSketches((all) => ({ ...all, [id]: state }));
  }, []);

  const halt = () => {
    worker.current?.terminate();
    worker.current = null;
    sound.current.close();
  };

  /** Run the drawing (or `drawing`: one just made from the code view, not on the board yet). */
  const start = useCallback(
    async (drawing?: SchematicData) => {
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
        pictures.current.clear();
        const w = new Worker(new URL("./sim.worker.ts", import.meta.url), { type: "module" });
        worker.current = w;
        w.onmessage = (event: MessageEvent<Reply>) => {
          if (worker.current !== w) return;
          const r = event.data;
          if (r.type === "frame") received(r.frame, r.behind);
          else if (r.type === "pictures")
            for (const [id, image] of Object.entries(r.pictures)) pictures.current.put(id, image);
          else {
            setError(
              r.message.includes("NoConvergence") && r.time !== null
                ? { data: r.message, issue: { type: "NoConvergence", time: r.time } }
                : { data: r.message },
            );
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
          type: "start",
          circuit: compiled,
          parts: partsOf(latest.current),
          pressed: [...pressed.current],
          speed: speedRef.current,
          scope: first,
          probe: probeRef.current,
        } satisfies Request);
        setStatus("running");
        for (const e of latest.current.elements) if (e.kind === "arduino" || e.kind === "pico") void upload(e.id);
      } catch (e) {
        setError({ data: String(e) });
        setStatus("off");
      }
    },
    [received, upload],
  );

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

  /** A Pico's program given whole (a file the user dropped: its flash image), on the board now — ``text``:
   *  the board's text as it will be (naming the file). Not running, it starts with the simulation (from the text). */
  const runFile = useCallback((id: string, image: Uint8Array, text: string) => {
    const w = worker.current;
    if (!w) return;
    w.postMessage({ type: "attach", id, firmware: { board: "pico", image } } satisfies Request);
    setSketches((all) => ({ ...all, [id]: { kind: "running", sketch: text, where: "file" } }));
  }, []);

  return {
    status,
    error,
    frame,
    speed,
    traces,
    scope,
    serial,
    sketches,
    start,
    runFile,
    stop,
    setSpeed: (value: number) => {
      setSpeedState(value);
      tell({ type: "speed", speed: value });
    },
    pause: () => {
      tell({ type: "run", running: false });
      setStatus((s) => (s === "running" ? "paused" : s));
    },
    resume: () => {
      wake();
      setError(null);
      tell({ type: "run", running: true });
      setStatus((s) => (s === "paused" ? "running" : s));
    },
    /** A buzzer in the circuit (the bar offers to mute it); muted, whether it is. */
    hasSound,
    muted,
    setMuted: (quiet: boolean) => {
      if (!quiet) wake();
      setMuted(quiet);
    },
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
      const nodes = Object.keys(c.program.nodes)
        .filter((n) => n !== "GND")
        .map((n) => `V_${n}`);
      const parts = Object.entries(c.program.parts).flatMap(([, q]) =>
        Object.values(q).map((i) => c.program.unknowns[i]),
      );
      return [...nodes, ...parts.filter((n) => !nodes.includes(n))];
    },
    upload,
    /** Whether the board can be seen (scrolled out of view: it runs, but nothing is sent to draw). */
    setOnScreen: useCallback((seen: boolean) => tell({ type: "visible", visible: seen }), []),
    /** The error shown under the board, away (it comes back if it happens again). */
    dismissError: () => setError(null),
    clearSerial: () => {
      serialText.current = "";
      setSerial("");
    },
    /** Text typed into the serial monitor: to every Arduino's Serial.read(). */
    sendSerial: (text: string) => tell({ type: "send", text }),
  };
}

export type Live = ReturnType<typeof useLive>;
