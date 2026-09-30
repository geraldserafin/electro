"""A simulation's waveforms as SVG: ``trace.plot("V_A", "I_LED_1")``, or a trace on its own in a notebook.

Voltages and currents never share an axis: each gets its own panel, one above the other, on
the same time axis. Lines are 2 px in a fixed series order; with several series a legend on
top, and each line's name at its end. No words, only symbols and units, so any language reads it.
"""

from __future__ import annotations

import math
from html import escape

# categorical slots (light, dark), in this order: blue, orange, aqua, yellow, magenta, green
SERIES = [
    ("#2a78d6", "#3987e5"),
    ("#eb6834", "#d95926"),
    ("#1baf7a", "#199e70"),
    ("#eda100", "#c98500"),
    ("#e87ba4", "#d55181"),
    ("#008300", "#008300"),
]
WIDTH, PANEL, LEFT, RIGHT, TOP = 640, 150, 52, 76, 26
MAX_POINTS = 1200

_PREFIXES = [(1e6, "M"), (1e3, "k"), (1, ""), (1e-3, "m"), (1e-6, "µ"), (1e-9, "n")]


def _scale(largest: float) -> tuple[float, str]:
    """A factor and SI prefix so that ``largest`` reads in units, not 0.0000x."""
    for factor, prefix in _PREFIXES:
        if largest >= factor * 0.999 or factor == 1e-9:
            return factor, prefix
    return 1, ""


def _ticks(lo: float, hi: float, count: int = 5) -> list[float]:
    if hi - lo < 1e-12:
        lo, hi = lo - 1, hi + 1
    raw = (hi - lo) / count
    step = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 2.5, 5, 10):
        if m * step >= raw:
            step *= m
            break
    first = math.floor(lo / step) * step
    ticks, v = [], first
    while v <= hi + step * 1e-6:
        ticks.append(round(v, 12))
        v += step
    return ticks


def _num(v: float) -> str:
    return f"{v:.4g}".replace("-", "−")


def _decimate(t: list[float], y: list[float]) -> list[tuple[float, float]]:
    """At most ``MAX_POINTS`` points, keeping each bucket's lowest and highest (spikes stay)."""
    if len(t) <= MAX_POINTS:
        return list(zip(t, y))
    out, size = [], len(t) / (MAX_POINTS / 2)
    for b in range(MAX_POINTS // 2):
        i0, i1 = int(b * size), min(len(t), int((b + 1) * size))
        if i0 >= i1:
            continue
        lo = min(range(i0, i1), key=y.__getitem__)
        hi = max(range(i0, i1), key=y.__getitem__)
        out += [(t[i], y[i]) for i in sorted({lo, hi})]
    return out


def _label(name: str) -> str:
    """``V_A`` → V<sub>A</sub>; ``I_LED_1`` → I<sub>LED_1</sub>."""
    head, _, sub = name.partition("_")
    return f'{escape(head)}<tspan class="sub" dy="3">{escape(sub)}</tspan>' if sub else escape(head)


def _open(uid: str, height: int) -> list[str]:
    """The ``<svg>`` and its styles: series colours in both themes, text, grid and axis lines."""
    style = "".join(
        f".{uid} .s{k}{{stroke:{light}}}.{uid} .k{k}{{fill:{light}}}" for k, (light, _) in enumerate(SERIES)
    )
    style += "".join(
        f':root[data-theme="dark"] .{uid} .s{k}{{stroke:{dark}}}:root[data-theme="dark"] .{uid} .k{k}{{fill:{dark}}}'
        for k, (_, dark) in enumerate(SERIES)
    )
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" class="{uid}" width="{WIDTH}" height="{height}" '
        f'viewBox="0 0 {WIDTH} {height}" font-family="ui-sans-serif,system-ui,sans-serif" font-size="11">',
        f"<style>{style}.{uid} text{{fill:currentColor}}.{uid} .muted{{opacity:.62}}"
        f".{uid} .grid{{stroke:currentColor;opacity:.12;stroke-width:1}}"
        f".{uid} .axis{{stroke:currentColor;opacity:.35;stroke-width:1}}"
        f".{uid} .line{{fill:none;stroke-width:2;stroke-linejoin:round;stroke-linecap:round}}"
        f".{uid} .sub{{font-size:8px}}</style>",
    ]


class TracePlot:
    def __init__(self, trace, names: list[str]):
        self.trace, self.names = trace, names

    def _repr_svg_(self) -> str:
        trace = self.trace
        volts = [n for n in self.names if not n.startswith("I_")]
        amps = [n for n in self.names if n.startswith("I_")]
        panels = [(group, unit) for group, unit in ((volts, "V"), (amps, "A")) if group]
        t = trace.t  # the x axis: time, or what a sweep changes (``x_name``, ``x_unit``)
        t_start, t_end = (t[0], t[-1]) if t else (0.0, 1.0)
        t_factor, t_prefix = _scale(max(abs(t_start), abs(t_end)))
        x_name, x_unit = getattr(trace, "x_name", "t"), getattr(trace, "x_unit", "s")
        height = TOP + len(panels) * (PANEL + 48) + 10
        w = WIDTH - LEFT - RIGHT
        uid = f"tp{id(self) % 100000}"
        colors = {n: k for k, n in enumerate(self.names)}
        parts = _open(uid, height)
        if self.names:  # legend: a short line-key and the name, in text ink
            x = LEFT
            for n in self.names:
                k = colors[n] % len(SERIES)
                parts.append(
                    f'<rect class="k{k}" x="{x}" y="9" width="14" height="3" rx="1.5"/>'
                    f'<text x="{x + 19}" y="14">{_label(n)}</text>'
                )
                x += 30 + 7 * len(n)
        y0 = TOP
        for group, unit in panels:
            series = {n: trace[n] for n in group}
            lo = min(min(v) for v in series.values())
            hi = max(max(v) for v in series.values())
            factor, prefix = _scale(max(abs(lo), abs(hi)))
            lo, hi = lo / factor, hi / factor
            if unit == "V" or lo >= 0:
                lo = min(lo, 0.0)
            ticks = _ticks(lo, hi)
            lo, hi = min(lo, ticks[0]), max(hi, ticks[-1])
            sy = lambda v, lo=lo, hi=hi, y0=y0: y0 + PANEL - (v - lo) / (hi - lo or 1) * PANEL  # noqa: E731
            sx = lambda s: LEFT + (s - t_start) / ((t_end - t_start) or 1) * w  # noqa: E731
            for v in ticks:
                y = sy(v)
                parts.append(
                    f'<line class="grid" x1="{LEFT}" x2="{LEFT + w}" y1="{y:.1f}" y2="{y:.1f}"/>'
                    f'<text class="muted" x="{LEFT - 6}" y="{y + 3.5:.1f}" text-anchor="end">{_num(v)}</text>'
                )
            parts.append(f'<text class="muted" x="{LEFT - 6}" y="{y0 - 8}" text-anchor="end">{prefix}{unit}</text>')
            ends = []
            for n, values in series.items():
                k = colors[n] % len(SERIES)
                pts = _decimate(t, values)
                path = " ".join(f"{sx(a):.1f},{sy(b / factor):.1f}" for a, b in pts)
                parts.append(f'<polyline class="line s{k}" points="{path}"><title>{escape(n)}</title></polyline>')
                ends.append([sy(values[-1] / factor), n])
            if len(self.names) <= 4 and len(self.names) > 1:  # each line's name at its end, spread apart
                ends.sort()
                for i in range(1, len(ends)):
                    ends[i][0] = max(ends[i][0], ends[i - 1][0] + 13)
                for y, n in ends:
                    parts.append(f'<text x="{LEFT + w + 6}" y="{y + 3.5:.1f}">{_label(n)}</text>')
            parts.append(f'<line class="axis" x1="{LEFT}" x2="{LEFT + w}" y1="{y0 + PANEL}" y2="{y0 + PANEL}"/>')
            span = (t_end - t_start) * 1e-4
            for v in _ticks(t_start / t_factor, t_end / t_factor):
                if not t_start - span <= v * t_factor <= t_end + span:
                    continue
                x = sx(v * t_factor)
                parts.append(
                    f'<text class="muted" x="{x:.1f}" y="{y0 + PANEL + 15}" text-anchor="middle">{_num(v)}</text>'
                )
            parts.append(
                f'<text class="muted" x="{LEFT + w + 16}" y="{y0 + PANEL + 15}">{_label(x_name)} [{t_prefix}{x_unit}]</text>'
            )
            y0 += PANEL + 48
        parts.append("</svg>")
        return "".join(parts)


_SI = [(1e9, "G"), (1e6, "M"), (1e3, "k"), (1, ""), (1e-3, "m")]


def _hz(f: float) -> str:
    """1000 → 1k, 2.5e6 → 2.5M."""
    for factor, prefix in _SI:
        if f >= factor * 0.999:
            return f"{f / factor:.3g}{prefix}"
    return _num(f)


class BodePlot:
    """A frequency response as two panels on a logarithmic frequency axis: |H| in dB, then its phase."""

    def __init__(self, response):
        self.response = response

    def _repr_svg_(self) -> str:
        r = self.response
        names = list(r.values)
        gains, phases = r.gain_db, r.phase_deg
        f, panels = r.f, [(gains, "dB"), (phases, "°")]
        lo_f, hi_f = math.log10(f[0]), math.log10(f[-1])
        height = TOP + len(panels) * (PANEL + 48) + 10
        w = WIDTH - LEFT - RIGHT
        uid = f"bp{id(self) % 100000}"
        sx = lambda v: LEFT + (math.log10(v) - lo_f) / (hi_f - lo_f or 1) * w  # noqa: E731
        parts = _open(uid, height)
        x = LEFT + 4  # legend: each output (per the input, if there is one), a key in its colour
        for k, n in enumerate(names):
            key = (
                f'<rect class="k{k % len(SERIES)}" x="{x}" y="9" width="14" height="3" rx="1.5"/>'
                if len(names) > 1
                else ""
            )
            per = f" / {_label(r.input)}" if r.input else ""
            parts.append(f'{key}<text x="{x + (19 if key else 0)}" y="14">{_label(n)}{per}</text>')
            x += 40 + 7 * (len(n) + (len(r.input) + 3 if r.input else 0))
        decades = [10.0**k for k in range(math.ceil(lo_f - 1e-9), math.floor(hi_f + 1e-9) + 1)]
        y0 = TOP
        for series, unit in panels:
            lo = min(min(v) for v in series.values())
            hi = max(max(v) for v in series.values())
            if unit == "°":  # phase in steps of 45° (90° past a half turn)
                step = 45 if hi - lo <= 180 else 90
                lo, hi = step * math.floor(lo / step + 1e-9), step * math.ceil(hi / step - 1e-9)
                if hi == lo:
                    lo, hi = lo - step, hi + step
                ticks = [lo + step * i for i in range(round((hi - lo) / step) + 1)]
            else:
                ticks = _ticks(lo, hi)
                if len(ticks) > 1 and ticks[-1] < hi - 1e-9:  # a tick above the top too (−0.05 dB: up to 0)
                    ticks.append(ticks[-1] + ticks[1] - ticks[0])
                lo, hi = min(lo, ticks[0]), max(hi, ticks[-1])
            sy = lambda v, lo=lo, hi=hi, y0=y0: y0 + PANEL - (v - lo) / (hi - lo or 1) * PANEL  # noqa: E731
            for v in ticks:
                y = sy(v)
                parts.append(
                    f'<line class="grid" x1="{LEFT}" x2="{LEFT + w}" y1="{y:.1f}" y2="{y:.1f}"/>'
                    f'<text class="muted" x="{LEFT - 6}" y="{y + 3.5:.1f}" text-anchor="end">{_num(v)}</text>'
                )
            for d in decades:
                x = sx(d)
                parts.append(
                    f'<line class="grid" x1="{x:.1f}" x2="{x:.1f}" y1="{y0}" y2="{y0 + PANEL}"/>'
                    f'<text class="muted" x="{x:.1f}" y="{y0 + PANEL + 15}" text-anchor="middle">{_hz(d)}</text>'
                )
            parts.append(f'<text class="muted" x="{LEFT - 6}" y="{y0 - 8}" text-anchor="end">{unit}</text>')
            if unit == "dB":  # the −3 dB corners of the first output, marked and named
                for fc in r.cutoffs():
                    x = sx(fc)
                    parts.append(
                        f'<line class="axis" x1="{x:.1f}" x2="{x:.1f}" y1="{y0}" y2="{y0 + PANEL}" stroke-dasharray="4 3"/>'
                        f'<text x="{x + 4:.1f}" y="{y0 + PANEL - 6}">f<tspan class="sub" dy="3">g</tspan>'
                        f'<tspan dy="-3"> = {_hz(fc)}Hz</tspan></text>'
                    )
            for k, n in enumerate(names):
                path = " ".join(f"{sx(a):.1f},{sy(b):.1f}" for a, b in zip(f, series[n]))
                parts.append(
                    f'<polyline class="line s{k % len(SERIES)}" points="{path}"><title>{escape(n)}</title></polyline>'
                )
            parts.append(f'<line class="axis" x1="{LEFT}" x2="{LEFT + w}" y1="{y0 + PANEL}" y2="{y0 + PANEL}"/>')
            parts.append(f'<text class="muted" x="{LEFT + w + 16}" y="{y0 + PANEL + 15}">f [Hz]</text>')
            y0 += PANEL + 48
        parts.append("</svg>")
        return "".join(parts)


class HistogramPlot:
    """A spread (``analysis.Spread``) as one histogram per output: how many builds gave each value,
    in 24 bins, the mean marked; its unit's prefix as on the traces."""

    BINS = 24

    def __init__(self, spread):
        self.spread = spread

    def _repr_svg_(self) -> str:
        names = list(self.spread.values)
        height = TOP + len(names) * (PANEL + 48) + 10
        w = WIDTH - LEFT - RIGHT
        uid = f"hp{id(self) % 100000}"
        parts = _open(uid, height)
        y0 = TOP
        for k, name in enumerate(names):
            v = self.spread.values[name]
            lo, hi = min(v), max(v)
            span = (hi - lo) or abs(hi) or 1.0
            counts = [0] * self.BINS
            for x in v:
                counts[min(self.BINS - 1, int((x - lo) / span * self.BINS))] += 1
            top = max(counts)
            factor, prefix = _scale(max(abs(lo), abs(hi)))
            unit = "A" if name.startswith("I_") else "V"
            bar = w / self.BINS
            parts.append(f'<text x="{LEFT}" y="{y0 - 10}">{_label(name)}</text>')
            for i, n in enumerate(counts):
                h = n / top * PANEL
                parts.append(
                    f'<rect class="k{k % len(SERIES)}" x="{LEFT + i * bar + 1:.1f}" y="{y0 + PANEL - h:.1f}" '
                    f'width="{bar - 2:.1f}" height="{h:.1f}" rx="1.5"/>'
                )
            mean = sum(v) / len(v)
            xm = LEFT + (mean - lo) / span * w
            parts.append(
                f'<line x1="{xm:.1f}" x2="{xm:.1f}" y1="{y0 - 4}" y2="{y0 + PANEL}" stroke="currentColor" '
                f'stroke-width="1.5" stroke-dasharray="4 3"><title>{_num(mean / factor)} {prefix}{unit}</title></line>'
            )
            parts.append(f'<line class="axis" x1="{LEFT}" x2="{LEFT + w}" y1="{y0 + PANEL}" y2="{y0 + PANEL}"/>')
            for t in _ticks(lo / factor, hi / factor):
                if lo / factor - 1e-12 <= t <= hi / factor + 1e-12:
                    x = LEFT + (t * factor - lo) / span * w
                    parts.append(
                        f'<text class="muted" x="{x:.1f}" y="{y0 + PANEL + 15}" text-anchor="middle">{_num(t)}</text>'
                    )
            parts.append(f'<text class="muted" x="{LEFT + w + 16}" y="{y0 + PANEL + 15}">{prefix}{unit}</text>')
            y0 += PANEL + 48
        parts.append("</svg>")
        return "".join(parts)
