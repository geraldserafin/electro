// Plots as SVG, from the numbers the kernel sends: waveforms over time (or over what a sweep changes), a
// frequency response (Bode), a spread over many builds (a histogram). Voltages and currents never share an
// axis; lines 2 px in a fixed series order; a legend when there are several. No words, only symbols and
// units, so any language reads it.

/** Categorical slots (light, dark), in this order: blue, orange, aqua, yellow, magenta, green. */
const SERIES: [string, string][] = [
  ["#2a78d6", "#3987e5"],
  ["#eb6834", "#d95926"],
  ["#1baf7a", "#199e70"],
  ["#eda100", "#c98500"],
  ["#e87ba4", "#d55181"],
  ["#008300", "#008300"],
];
const WIDTH = 640,
  PANEL = 150,
  LEFT = 52,
  RIGHT = 76,
  TOP = 26,
  MAX_POINTS = 1200,
  BINS = 24;
const PREFIXES: [number, string][] = [
  [1e6, "M"],
  [1e3, "k"],
  [1, ""],
  [1e-3, "m"],
  [1e-6, "µ"],
  [1e-9, "n"],
];
const SI: [number, string][] = [
  [1e9, "G"],
  [1e6, "M"],
  [1e3, "k"],
  [1, ""],
  [1e-3, "m"],
];

export interface TraceData {
  x: { name: string; unit: string };
  t: number[];
  series: Record<string, number[]>;
}

export interface BodeData {
  f: number[];
  input: string | null;
  outputs: Record<string, { gain: number[]; phase: number[] }>;
  cutoffs: number[];
}

export interface HistogramData {
  values: Record<string, number[]>;
}

let plots = 0;

/** A factor and SI prefix so that ``largest`` reads in units, not 0.0000x. */
function scale(largest: number): [number, string] {
  for (const [factor, prefix] of PREFIXES) if (largest >= factor * 0.999 || factor === 1e-9) return [factor, prefix];
  return [1, ""];
}

function ticks(lo: number, hi: number, count = 5): number[] {
  if (hi - lo < 1e-12) [lo, hi] = [lo - 1, hi + 1];
  const raw = (hi - lo) / count;
  let step = 10 ** Math.floor(Math.log10(raw));
  for (const m of [1, 2, 2.5, 5, 10])
    if (m * step >= raw) {
      step *= m;
      break;
    }
  const out: number[] = [];
  for (let v = Math.floor(lo / step) * step; v <= hi + step * 1e-6; v += step) out.push(Math.round(v * 1e12) / 1e12);
  return out;
}

const num = (v: number) => Number(v.toPrecision(4)).toString().replace("-", "−");
const fixed = (v: number) => v.toFixed(1);
const escapeXml = (text: string) =>
  text.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!);

/** ``V_A`` → V<sub>A</sub>. */
function label(name: string): string {
  const [head, ...rest] = name.split("_");
  const sub = rest.join("_");
  return sub ? `${escapeXml(head)}<tspan class="sub" dy="3">${escapeXml(sub)}</tspan>` : escapeXml(head);
}

function hz(f: number): string {
  for (const [factor, prefix] of SI) if (f >= factor * 0.999) return `${Number((f / factor).toPrecision(3))}${prefix}`;
  return num(f);
}

/** At most ``MAX_POINTS`` points, each bucket's lowest and highest kept (spikes stay). */
function decimate(t: number[], y: number[]): [number, number][] {
  if (t.length <= MAX_POINTS) return t.map((s, i) => [s, y[i]]);
  const out: [number, number][] = [];
  const size = t.length / (MAX_POINTS / 2);
  for (let b = 0; b < MAX_POINTS / 2; b++) {
    const [i0, i1] = [Math.floor(b * size), Math.min(t.length, Math.floor((b + 1) * size))];
    if (i0 >= i1) continue;
    let lo = i0,
      hi = i0;
    for (let i = i0; i < i1; i++) {
      if (y[i] < y[lo]) lo = i;
      if (y[i] > y[hi]) hi = i;
    }
    for (const i of [...new Set([lo, hi])].sort((a, b) => a - b)) out.push([t[i], y[i]]);
  }
  return out;
}

/** The ``<svg>`` and its styles: series colours in both themes, text, grid and axis lines. */
function open(uid: string, height: number): string[] {
  const style =
    SERIES.map(([light], k) => `.${uid} .s${k}{stroke:${light}}.${uid} .k${k}{fill:${light}}`).join("") +
    SERIES.map(
      ([, dark], k) =>
        `:root[data-theme="dark"] .${uid} .s${k}{stroke:${dark}}:root[data-theme="dark"] .${uid} .k${k}{fill:${dark}}`,
    ).join("");
  return [
    `<svg xmlns="http://www.w3.org/2000/svg" class="${uid}" width="${WIDTH}" height="${height}" viewBox="0 0 ${WIDTH} ${height}" font-family="ui-sans-serif,system-ui,sans-serif" font-size="11">`,
    `<style>${style}.${uid} text{fill:currentColor}.${uid} .muted{opacity:.62}` +
      `.${uid} .grid{stroke:currentColor;opacity:.12;stroke-width:1}` +
      `.${uid} .axis{stroke:currentColor;opacity:.35;stroke-width:1}` +
      `.${uid} .line{fill:none;stroke-width:2;stroke-linejoin:round;stroke-linecap:round}` +
      `.${uid} .sub{font-size:8px}</style>`,
  ];
}

function legend(names: string[]): string[] {
  let x = LEFT;
  return names.map((n, k) => {
    const out = `<rect class="k${k % SERIES.length}" x="${x}" y="9" width="14" height="3" rx="1.5"/><text x="${x + 19}" y="14">${label(n)}</text>`;
    x += 30 + 7 * n.length;
    return out;
  });
}

/** Waveforms: voltages in one panel, currents in another, over one axis (time, or a swept value). */
export function traceSvg({ x, t, series }: TraceData): string {
  const names = Object.keys(series);
  const volts = names.filter((n) => !n.startsWith("I_"));
  const amps = names.filter((n) => n.startsWith("I_"));
  const panels = (
    [
      [volts, "V"],
      [amps, "A"],
    ] as const
  ).filter(([group]) => group.length);
  const [start, end] = t.length ? [t[0], t[t.length - 1]] : [0, 1];
  const [tFactor, tPrefix] = scale(Math.max(Math.abs(start), Math.abs(end)));
  const height = TOP + panels.length * (PANEL + 48) + 10;
  const w = WIDTH - LEFT - RIGHT;
  const uid = `tp${++plots}`;
  const parts = [...open(uid, height), ...(names.length ? legend(names) : [])];
  const sx = (s: number) => LEFT + ((s - start) / (end - start || 1)) * w;
  let y0 = TOP;
  for (const [group, unit] of panels) {
    const values = group.flatMap((n) => series[n]);
    let lo = Math.min(...values),
      hi = Math.max(...values);
    const [factor, prefix] = scale(Math.max(Math.abs(lo), Math.abs(hi)));
    [lo, hi] = [lo / factor, hi / factor];
    if (unit === "V" || lo >= 0) lo = Math.min(lo, 0);
    const marks = ticks(lo, hi);
    [lo, hi] = [Math.min(lo, marks[0]), Math.max(hi, marks[marks.length - 1])];
    const top = y0;
    const sy = (v: number) => top + PANEL - ((v - lo) / (hi - lo || 1)) * PANEL;
    for (const v of marks)
      parts.push(
        `<line class="grid" x1="${LEFT}" x2="${LEFT + w}" y1="${fixed(sy(v))}" y2="${fixed(sy(v))}"/>` +
          `<text class="muted" x="${LEFT - 6}" y="${fixed(sy(v) + 3.5)}" text-anchor="end">${num(v)}</text>`,
      );
    parts.push(`<text class="muted" x="${LEFT - 6}" y="${y0 - 8}" text-anchor="end">${prefix}${unit}</text>`);
    const ends: [number, string][] = [];
    for (const n of group) {
      const k = names.indexOf(n) % SERIES.length;
      const path = decimate(t, series[n])
        .map(([a, b]) => `${fixed(sx(a))},${fixed(sy(b / factor))}`)
        .join(" ");
      parts.push(`<polyline class="line s${k}" points="${path}"><title>${escapeXml(n)}</title></polyline>`);
      ends.push([sy(series[n][series[n].length - 1] / factor), n]);
    }
    if (names.length > 1 && names.length <= 4) {
      ends.sort((a, b) => a[0] - b[0]);
      for (let i = 1; i < ends.length; i++) ends[i][0] = Math.max(ends[i][0], ends[i - 1][0] + 13);
      for (const [y, n] of ends) parts.push(`<text x="${LEFT + w + 6}" y="${fixed(y + 3.5)}">${label(n)}</text>`);
    }
    parts.push(`<line class="axis" x1="${LEFT}" x2="${LEFT + w}" y1="${y0 + PANEL}" y2="${y0 + PANEL}"/>`);
    const span = (end - start) * 1e-4;
    for (const v of ticks(start / tFactor, end / tFactor)) {
      if (!(start - span <= v * tFactor && v * tFactor <= end + span)) continue;
      parts.push(
        `<text class="muted" x="${fixed(sx(v * tFactor))}" y="${y0 + PANEL + 15}" text-anchor="middle">${num(v)}</text>`,
      );
    }
    parts.push(
      `<text class="muted" x="${LEFT + w + 16}" y="${y0 + PANEL + 15}">${label(x.name)} [${tPrefix}${x.unit}]</text>`,
    );
    y0 += PANEL + 48;
  }
  parts.push("</svg>");
  return parts.join("");
}

/** A frequency response: its gain in dB and its phase, on a logarithmic frequency axis. */
export function bodeSvg({ f, input, outputs, cutoffs }: BodeData): string {
  const names = Object.keys(outputs);
  const [loF, hiF] = [Math.log10(f[0]), Math.log10(f[f.length - 1])];
  const height = TOP + 2 * (PANEL + 48) + 10;
  const w = WIDTH - LEFT - RIGHT;
  const uid = `bp${++plots}`;
  const sx = (v: number) => LEFT + ((Math.log10(v) - loF) / (hiF - loF || 1)) * w;
  const parts = open(uid, height);
  let x = LEFT + 4;
  names.forEach((n, k) => {
    const key =
      names.length > 1 ? `<rect class="k${k % SERIES.length}" x="${x}" y="9" width="14" height="3" rx="1.5"/>` : "";
    const per = input ? ` / ${label(input)}` : "";
    parts.push(`${key}<text x="${x + (key ? 19 : 0)}" y="14">${label(n)}${per}</text>`);
    x += 40 + 7 * (n.length + (input ? input.length + 3 : 0));
  });
  const decades: number[] = [];
  for (let k = Math.ceil(loF - 1e-9); k <= Math.floor(hiF + 1e-9); k++) decades.push(10 ** k);
  let y0 = TOP;
  for (const which of ["gain", "phase"] as const) {
    const unit = which === "gain" ? "dB" : "°";
    const values = names.flatMap((n) => outputs[n][which]);
    let lo = Math.min(...values),
      hi = Math.max(...values);
    let marks: number[];
    if (which === "phase") {
      const step = hi - lo <= 180 ? 45 : 90;
      [lo, hi] = [step * Math.floor(lo / step + 1e-9), step * Math.ceil(hi / step - 1e-9)];
      if (hi === lo) [lo, hi] = [lo - step, hi + step];
      marks = Array.from({ length: Math.round((hi - lo) / step) + 1 }, (_, i) => lo + step * i);
    } else {
      marks = ticks(lo, hi);
      if (marks.length > 1 && marks[marks.length - 1] < hi - 1e-9)
        marks.push(marks[marks.length - 1] + marks[1] - marks[0]);
      [lo, hi] = [Math.min(lo, marks[0]), Math.max(hi, marks[marks.length - 1])];
    }
    const top = y0;
    const sy = (v: number) => top + PANEL - ((v - lo) / (hi - lo || 1)) * PANEL;
    for (const v of marks)
      parts.push(
        `<line class="grid" x1="${LEFT}" x2="${LEFT + w}" y1="${fixed(sy(v))}" y2="${fixed(sy(v))}"/>` +
          `<text class="muted" x="${LEFT - 6}" y="${fixed(sy(v) + 3.5)}" text-anchor="end">${num(v)}</text>`,
      );
    for (const d of decades)
      parts.push(
        `<line class="grid" x1="${fixed(sx(d))}" x2="${fixed(sx(d))}" y1="${y0}" y2="${y0 + PANEL}"/>` +
          `<text class="muted" x="${fixed(sx(d))}" y="${y0 + PANEL + 15}" text-anchor="middle">${hz(d)}</text>`,
      );
    parts.push(`<text class="muted" x="${LEFT - 6}" y="${y0 - 8}" text-anchor="end">${unit}</text>`);
    if (which === "gain")
      for (const fc of cutoffs) {
        const cx = sx(fc);
        parts.push(
          `<line class="axis" x1="${fixed(cx)}" x2="${fixed(cx)}" y1="${y0}" y2="${y0 + PANEL}" stroke-dasharray="4 3"/>` +
            `<text x="${fixed(cx + 4)}" y="${y0 + PANEL - 6}">f<tspan class="sub" dy="3">g</tspan><tspan dy="-3"> = ${hz(fc)}Hz</tspan></text>`,
        );
      }
    names.forEach((n, k) => {
      const path = f.map((a, i) => `${fixed(sx(a))},${fixed(sy(outputs[n][which][i]))}`).join(" ");
      parts.push(
        `<polyline class="line s${k % SERIES.length}" points="${path}"><title>${escapeXml(n)}</title></polyline>`,
      );
    });
    parts.push(`<line class="axis" x1="${LEFT}" x2="${LEFT + w}" y1="${y0 + PANEL}" y2="${y0 + PANEL}"/>`);
    parts.push(`<text class="muted" x="${LEFT + w + 16}" y="${y0 + PANEL + 15}">f [Hz]</text>`);
    y0 += PANEL + 48;
  }
  parts.push("</svg>");
  return parts.join("");
}

/** A spread: per output, how many builds gave each value, in ``BINS`` bins, the mean marked. */
export function histogramSvg({ values }: HistogramData): string {
  const names = Object.keys(values);
  const height = TOP + names.length * (PANEL + 48) + 10;
  const w = WIDTH - LEFT - RIGHT;
  const parts = open(`hp${++plots}`, height);
  let y0 = TOP;
  names.forEach((name, k) => {
    const v = values[name];
    const [lo, hi] = [Math.min(...v), Math.max(...v)];
    const span = hi - lo || Math.abs(hi) || 1;
    const counts = new Array<number>(BINS).fill(0);
    for (const x of v) counts[Math.min(BINS - 1, Math.floor(((x - lo) / span) * BINS))]++;
    const most = Math.max(...counts);
    const [factor, prefix] = scale(Math.max(Math.abs(lo), Math.abs(hi)));
    const unit = name.startsWith("I_") ? "A" : "V";
    const bar = w / BINS;
    parts.push(`<text x="${LEFT}" y="${y0 - 10}">${label(name)}</text>`);
    counts.forEach((n, i) => {
      const h = (n / most) * PANEL;
      parts.push(
        `<rect class="k${k % SERIES.length}" x="${fixed(LEFT + i * bar + 1)}" y="${fixed(y0 + PANEL - h)}" width="${fixed(bar - 2)}" height="${fixed(h)}" rx="1.5"/>`,
      );
    });
    const mean = v.reduce((s, x) => s + x, 0) / v.length;
    const xm = LEFT + ((mean - lo) / span) * w;
    parts.push(
      `<line x1="${fixed(xm)}" x2="${fixed(xm)}" y1="${y0 - 4}" y2="${y0 + PANEL}" stroke="currentColor" stroke-width="1.5" stroke-dasharray="4 3"><title>${num(mean / factor)} ${prefix}${unit}</title></line>`,
    );
    parts.push(`<line class="axis" x1="${LEFT}" x2="${LEFT + w}" y1="${y0 + PANEL}" y2="${y0 + PANEL}"/>`);
    for (const t of ticks(lo / factor, hi / factor))
      if (lo / factor - 1e-12 <= t && t <= hi / factor + 1e-12)
        parts.push(
          `<text class="muted" x="${fixed(LEFT + ((t * factor - lo) / span) * w)}" y="${y0 + PANEL + 15}" text-anchor="middle">${num(t)}</text>`,
        );
    parts.push(`<text class="muted" x="${LEFT + w + 16}" y="${y0 + PANEL + 15}">${prefix}${unit}</text>`);
    y0 += PANEL + 48;
  });
  parts.push("</svg>");
  return parts.join("");
}
