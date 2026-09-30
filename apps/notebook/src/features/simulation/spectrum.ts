// The scope's other view: what frequencies the last moments are made of. The trace resampled
// evenly, a Hann window, an FFT; amplitudes as the signal's own (a 5 V sine is a peak of 5 V).
// The same as electro's trace.spectrum() in Python.

/** Radix-2 FFT in place (re, im of a power-of-two length). */
export function fft(re: Float64Array, im: Float64Array): void {
  const n = re.length;
  for (let i = 1, j = 0; i < n; i++) {
    let bit = n >> 1;
    for (; j & bit; bit >>= 1) j ^= bit;
    j |= bit;
    if (i < j) {
      [re[i], re[j]] = [re[j], re[i]];
      [im[i], im[j]] = [im[j], im[i]];
    }
  }
  for (let size = 2; size <= n; size <<= 1) {
    const step = (-2 * Math.PI) / size;
    for (let start = 0; start < n; start += size) {
      for (let k = 0; k < size / 2; k++) {
        const c = Math.cos(step * k),
          s = Math.sin(step * k);
        const a = start + k,
          b = a + size / 2;
        const tr = re[b] * c - im[b] * s,
          ti = re[b] * s + im[b] * c;
        re[b] = re[a] - tr;
        im[b] = im[a] - ti;
        re[a] += tr;
        im[a] += ti;
      }
    }
  }
}

/** ``v(t)`` between ``from`` and ``to``: each frequency (up to a quarter of the sampling rate,
 * which is about the steps' own) and its amplitude; the mean at 0 Hz. */
export function spectrum(t: number[], v: number[], from: number, to: number): { f: number[]; a: number[] } {
  const inside = t.filter((s) => s >= from && s <= to).length;
  let n = 64;
  while (n < inside && n < 4096) n <<= 1;
  const dt = (to - from) / n;
  const re = new Float64Array(n),
    im = new Float64Array(n);
  let i = 0;
  for (let k = 0; k < n; k++) {
    const s = from + k * dt;
    while (i + 1 < t.length - 1 && t[i + 1] <= s) i++;
    const j = Math.min(i + 1, t.length - 1);
    const f = t[j] === t[i] ? 0 : Math.min(1, Math.max(0, (s - t[i]) / (t[j] - t[i])));
    re[k] = (v[i] ?? 0) + f * ((v[j] ?? 0) - (v[i] ?? 0));
  }
  const mean = re.reduce((a, b) => a + b, 0) / n;
  let sum = 0;
  for (let k = 0; k < n; k++) {
    const w = 0.5 - 0.5 * Math.cos((2 * Math.PI * k) / n);
    re[k] = (re[k] - mean) * w;
    sum += w;
  }
  fft(re, im);
  const keep = n / 4;
  const f: number[] = [],
    a: number[] = [];
  for (let k = 0; k < keep; k++) {
    f.push(k / (dt * n));
    a.push(k === 0 ? Math.abs(mean) : (2 * Math.hypot(re[k], im[k])) / sum);
  }
  return { f, a };
}
