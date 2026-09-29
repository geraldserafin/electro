// The buzzers heard: an oscillator each (a square wave, as a buzzer's is), its pitch and loudness
// set as the board is drawn. The page may only make a sound after a click, so the audio wakes on
// the one that starts the simulation (wake()).

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

export class Sound {
  private voices = new Map<string, { osc: OscillatorNode; gain: GainNode }>();

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
      const osc = context.createOscillator(), gain = context.createGain();
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
    for (const { gain } of this.voices.values()) gain.gain.setTargetAtTime(0, context.currentTime, 0.01);
  }

  /** Stopped for good. */
  close() {
    for (const { osc, gain } of this.voices.values()) {
      osc.stop();
      osc.disconnect();
      gain.disconnect();
    }
    this.voices.clear();
  }
}
