/// <reference lib="webworker" />
// The simulation off the page's thread: a Runner stepped as the clock goes (times the speed), with
// all of a core to itself — the page only draws what it is sent, about 30 times a second.
import { NoConvergence } from "./engine";
import { Runner, type Firmware, type Frame, type Part } from "./runner";
import type { LiveCircuit } from "./engine";

export type Request =
  | { type: "start"; circuit: LiveCircuit; parts: Part[]; pressed: string[]; speed: number; scope: string[]; probe: string[] }
  | { type: "parts"; parts: Part[]; pressed: string[] } // a switch flipped, a slider moved, a button held
  | { type: "attach"; id: string; firmware: Firmware } // a board's program, compiled
  | { type: "speed"; speed: number }
  | { type: "run"; running: boolean } // paused, or going on
  | { type: "watch"; scope: string[]; probe: string[] }
  | { type: "send"; text: string } // to the serial ports
  | { type: "visible"; visible: boolean }; // the board off screen: it runs, but is not sent

export type Reply =
  | { type: "frame"; frame: Frame; behind: boolean }
  | { type: "pictures"; pictures: Record<string, Uint8ClampedArray> } // the TFTs' (their buffers handed over, not copied)
  | { type: "error"; message: string; time: number | null };

const BUDGET = 25; // ms of computing at a time, then the messages waiting are taken
const REST = 4; // ms to wait when it keeps up
const FRAME = 33; // ms between frames sent
// the TFTs' pictures apart from the frames: as soon as one is drawn whole (Doom: up to 35 a second, more than
// the frames), at most one each PICTURE ms; with each frame too, whole or not (a program drawing in small windows)
const PICTURE = 14;
const LAG = 0.05; // s (of the page's time) behind before it says so

let runner: Runner | null = null;
let running = false, visible = true, speed = 1;
let last = 0, sent = 0, pictured = 0, behindSince: number | null = null;
let waiting = false; // a tick is scheduled
const STEER = 250; // ms between telling the runner how busy it is
let steered = 0, busyMs = 0; // since when, and how much of it computing

const post = (reply: Reply, transfer: Transferable[] = []) => self.postMessage(reply, transfer);
const picture = (now: number, anyway = false) => {
  if (!runner || (!anyway && now - pictured < PICTURE)) return;
  const pictures = runner.pictures(anyway);
  if (!pictures) return;
  pictured = now;
  post({ type: "pictures", pictures }, Object.values(pictures).map((p) => p.buffer));
};
const send = (now: number) => {
  if (!runner) return;
  sent = now;
  post({ type: "frame", frame: runner.frame(), behind: behindSince !== null && now - behindSince > LAG * 1000 });
  picture(now, true);
};

// a tick right away when behind (a MessageChannel: setTimeout would wait at least 4 ms), else after a rest
const channel = new MessageChannel();
channel.port1.onmessage = () => tick();
function schedule(now: boolean) {
  if (waiting) return;
  waiting = true;
  if (now) channel.port2.postMessage(null);
  else setTimeout(() => channel.port2.postMessage(null), REST);
}

function tick() {
  waiting = false;
  if (!runner || !running) return;
  const { sim } = runner.session;
  const now = performance.now();
  const elapsed = Math.min(0.1, (now - last) / 1000); // (a long pause — a background tab — is not made up for)
  last = now;
  const target = sim.t + elapsed * speed;
  const dtMax = Math.max(1e-7, speed * 1e-3);
  try {
    while (sim.t < target - 1e-15) {
      runner.advanceTo(Math.min(target, sim.t + dtMax * 4), dtMax);
      const at = performance.now();
      if (visible) picture(at);
      if (visible && at - sent >= FRAME) send(at); // (on time, not only as a tick ends)
      if (at - now > BUDGET) break;
    }
  } catch (e) {
    running = false;
    post({ type: "error", message: String(e), time: e instanceof NoConvergence ? e.time : sim.t });
    send(now);
    return;
  }
  const lagging = sim.t < target - 1e-12;
  busyMs += performance.now() - now;
  if (now - steered >= STEER) {
    if (steered) runner.steer(busyMs / (now - steered), lagging);
    steered = now;
    busyMs = 0;
  }
  if (!lagging) behindSince = null;
  else behindSince ??= now;
  if (visible) picture(performance.now());
  if (visible && performance.now() - sent >= FRAME) send(performance.now());
  schedule(lagging);
}

self.onmessage = (event: MessageEvent<Request>) => {
  const r = event.data;
  if (r.type === "start") {
    runner = new Runner(r.circuit, r.parts);
    runner.setParts(r.parts, r.pressed);
    runner.watch(r.scope, r.probe);
    runner.speed = speed = r.speed;
    running = true;
    last = performance.now();
    behindSince = null;
    schedule(true);
    return;
  }
  if (!runner) return;
  if (r.type === "parts") runner.setParts(r.parts, r.pressed);
  else if (r.type === "attach") runner.attach(r.id, r.firmware);
  else if (r.type === "speed") runner.speed = speed = r.speed;
  else if (r.type === "watch") runner.watch(r.scope, r.probe);
  else if (r.type === "send") runner.send(r.text);
  else if (r.type === "visible") visible = r.visible;
  else if (r.type === "run") {
    running = r.running;
    last = performance.now();
    behindSince = null;
    if (running) schedule(true);
  }
  // paused, what changed shows at once (running, it does at the next frame anyway)
  if (!running && r.type !== "run" && r.type !== "visible") send(performance.now());
  if (r.type === "visible" && r.visible) send(performance.now());
};
