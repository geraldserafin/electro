// The buzzers heard: an oscillator each (a square wave, as a buzzer's is), its pitch and loudness
// set as the board is drawn. The speakers: what they played, chunk after chunk (play()), each a little
// after the last ends. The page may only make a sound after a click, so the audio wakes on the one that
// starts the simulation (wake()).

let context: AudioContext | null = null;

/** Called from a click: the audio may start from now on. */
export function wake() {
  try {
    context ??= new AudioContext();
    void context.resume();
  } catch {
    context = null; // no Web Audio here: silent
  }
}

const LOUD = 0.05; // a square wave at full scale is harsh: this is loud enough
const SPEAKER_LOUD = 0.6;
const AHEAD = 0.08; // s: a speaker's next chunk starts this far ahead (the frames come unevenly)
const BEHIND = 0.01,
  TOO_FAR = 0.5; // s: its chunks ahead less than this (the circuit fell behind) or more: they start anew

export class Sound {
  private voices = new Map<string, { osc: OscillatorNode; gain: GainNode }>();
  private streams = new Map<string, { gain: GainNode; next: number }>();

  /** A speaker's ``samples`` (at ``rate``, in the circuit's time; ``speed``: the circuit's time to the page's). */
  play(id: string, samples: Float32Array, rate: number, speed: number) {
    if (!context || !samples.length || speed <= 0) return;
    let stream = this.streams.get(id);
    if (!stream) {
      const gain = context.createGain();
      gain.connect(context.destination);
      this.streams.set(id, (stream = { gain, next: 0 }));
    }
    stream.gain.gain.setTargetAtTime(SPEAKER_LOUD, context.currentTime, 0.01);
    const buffer = context.createBuffer(1, samples.length, rate);
    buffer.copyToChannel(samples as Float32Array<ArrayBuffer>, 0);
    const source = context.createBufferSource();
    source.buffer = buffer;
    source.playbackRate.value = speed; // (slower time: lower, as a tape)
    source.connect(stream.gain);
    const now = context.currentTime;
    if (stream.next < now + BEHIND || stream.next > now + TOO_FAR) stream.next = now + AHEAD;
    source.start(stream.next);
    stream.next += buffer.duration / speed;
  }

  /** ``id`` sounds at ``frequency`` (Hz) and ``volume`` (0–1); null, or outside what is heard: silent. */
  set(id: string, frequency: number | null, volume: number) {
    if (!context) return;
    const now = context.currentTime;
    let voice = this.voices.get(id);
    if (frequency === null || frequency < 20 || frequency > 20000 || volume <= 0) {
      voice?.gain.gain.setTargetAtTime(0, now, 0.01);
      return;
    }
    if (!voice) {
      const osc = context.createOscillator(),
        gain = context.createGain();
      osc.type = "square";
      gain.gain.value = 0;
      osc.connect(gain).connect(context.destination);
      osc.start();
      this.voices.set(id, (voice = { osc, gain }));
    }
    voice.osc.frequency.setTargetAtTime(frequency, now, 0.005);
    voice.gain.gain.setTargetAtTime(LOUD * Math.min(1, volume), now, 0.01);
  }

  /** Every buzzer quiet (paused, muted); they sound again when set. */
  silence() {
    if (!context) return;
    for (const { gain } of [...this.voices.values(), ...this.streams.values()])
      gain.gain.setTargetAtTime(0, context.currentTime, 0.01);
  }

  /** Stopped for good. */
  close() {
    for (const { osc, gain } of this.voices.values()) {
      osc.stop();
      osc.disconnect();
      gain.disconnect();
    }
    this.voices.clear();
    for (const { gain } of this.streams.values()) gain.disconnect();
    this.streams.clear();
  }
}
