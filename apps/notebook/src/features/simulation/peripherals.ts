// What the page makes of a buzzer's and a servo's waveforms (electro.devices.Buzzer, Servo): the
// circuit gives their voltages step by step, these follow them — listen()/watch() after every
// step, heard()/turn() when the board is drawn.

const BUZZER_ON = 2.5,
  BUZZER_TONE = 2300; // an active buzzer: above this (V) it sounds, at this (Hz)
const SERVO_MIN = 544e-6,
  SERVO_MAX = 2400e-6; // s: 0° and 180° (Arduino's Servo library)
const SERVO_SPEED = 600; // °/s: 60° in 0.1 s, a small servo's
const LOGIC = 2.5; // V: a servo's signal is high above this

/** A buzzer listened to between two drawings of the board. */
export interface Buzzing {
  id: string;
  u: number; // its voltage's index in x
  active: boolean; // its own oscillator (electro's Buzzer), else it sounds as it is driven (PassiveBuzzer)
  on: number; // active: how long it was above BUZZER_ON (s)
  edges: number;
  above: boolean;
  peak: number;
  lastPeak: number; // passive: the waveform's rising edges, its peak
}

export const buzzing = (id: string, u: number, active: boolean): Buzzing => ({
  id,
  u,
  active,
  on: 0,
  edges: 0,
  above: false,
  peak: 0,
  lastPeak: 0,
});

/** One step of ``dt`` seconds ending at voltage ``u``. */
export function listen(b: Buzzing, u: number, dt: number) {
  if (b.active) {
    if (u > BUZZER_ON) b.on += dt;
    return;
  }
  const above = u > Math.max(0.2, b.lastPeak / 2); // half of what it swung to last time
  if (above && !b.above) b.edges++;
  b.above = above;
  b.peak = Math.max(b.peak, Math.abs(u));
}

/** What it sounded like over the last ``span`` seconds (then it listens anew): its pitch (null: silent), loudness 0–1. */
export function heard(b: Buzzing, span: number): { frequency: number | null; volume: number } {
  const frequency = b.active ? (b.on / span > 0.5 ? BUZZER_TONE : null) : b.edges >= 2 ? b.edges / span : null;
  const volume = b.active ? 1 : Math.min(1, b.peak / 5);
  Object.assign(b, { on: 0, edges: 0, lastPeak: b.peak, peak: 0 });
  return { frequency, volume };
}

/** A servo: its signal's pulses measured as they come, its arm moving towards what they ask. */
export interface Servoing {
  id: string;
  u: number; // its signal's index in x
  high: boolean;
  rose: number;
  last: number; // the signal now, when it went high, the time of the last sample
  target: number;
  angle: number;
  shown: number; // degrees; when the arm was last moved
}

export const servoing = (id: string, u: number): Servoing => ({
  id,
  u,
  high: false,
  rose: 0,
  last: 0,
  target: 90,
  angle: 90,
  shown: 0,
});

/**
 * The signal ``u`` at time ``t``. A pulse lasts from the last sample before it rose to the last before
 * it fell: exact for a pin's edges (a step ends where the pin changed), within a step for a slower signal.
 */
export function watch(m: Servoing, u: number, t: number) {
  const high = u > LOGIC;
  if (high && !m.high) m.rose = m.last;
  else if (!high && m.high) {
    const width = m.last - m.rose;
    if (width > 3e-4 && width < 3e-3)
      m.target = Math.max(0, Math.min(180, ((width - SERVO_MIN) / (SERVO_MAX - SERVO_MIN)) * 180));
  }
  m.high = high;
  m.last = t;
}

/** Its arm at time ``t``: as far towards the target as it can have turned since it was last moved. */
export function turn(m: Servoing, t: number): number {
  const step = SERVO_SPEED * Math.max(0, t - m.shown);
  m.angle += Math.max(-step, Math.min(step, m.target - m.angle));
  m.shown = t;
  return m.angle;
}

/** An HC-SR04: a trigger pulse of 10 µs, then an echo as long as the sound's way there and back. */
export interface Sonar {
  id: string;
  trig: number; // its trigger's voltage's index in x
  high: boolean;
  rose: number;
  last: number; // the trigger now, when it went high, the last sample's time
  until: number; // the echo it is sending lasts till then (a trigger meanwhile is not heard)
}

const SOUND = 343; // m/s
const RANGE = [2, 400]; // cm it measures; beyond, the echo times out
const TIMEOUT = 38e-3; // s: the echo when nothing came back
// s: from the trigger falling to the echo rising (the sensor's burst takes about this). More than
// a slice: a chip runs up to a slice ahead of the circuit (session.ts), and must not be past it.
export const ECHO_DELAY = 1.2e-3;

export const sonar = (id: string, trig: number): Sonar => ({ id, trig, high: false, rose: 0, last: 0, until: -1 });

/**
 * The trigger ``u`` at time ``t``; ``distance`` in cm. A ping (the trigger high for 10 µs, then low):
 * the echo to send, [when it rises, how long it lasts]; else null.
 */
export function ping(s: Sonar, u: number, t: number, distance: number): [number, number] | null {
  const high = u > LOGIC;
  let echo: [number, number] | null = null;
  if (high && !s.high) s.rose = s.last;
  else if (!high && s.high && s.last - s.rose >= 9e-6 && s.last >= s.until) {
    const length = distance >= RANGE[0] && distance <= RANGE[1] ? (2 * distance) / 100 / SOUND : TIMEOUT;
    echo = [s.last + ECHO_DELAY, length];
    s.until = s.last + ECHO_DELAY + length;
  }
  s.high = high;
  s.last = t;
  return echo;
}
