// One element on the drawing: its symbol, its label ("R_1 = 100 Ω", beside it where no wire runs),
// and after a run what was found (the solved value, I and U).
import {
  type CSSProperties,
  memo,
  type PointerEvent as ReactPointerEvent,
  useId,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import type { ElementData, ElementResult, Point, SymbolLibrary, WireData } from "@/shared/model/types";
import { hasValue, isBoard, isComponent, isWaveSource, keyLabel, kindInfo, pins, rotate, waveLabel } from "./model";
import { symbolOf } from "./parts";

/**
 * Where an element is grabbed: all of it as drawn (its body is not just its strokes — a module's
 * insides, an LCD's glass), and its pins; at least 24 px across, so a thin one (a resistor) is too.
 */
function hitArea(box: DOMRect | null, xs: number[], ys: number[]) {
  const x0 = Math.min(box?.x ?? Infinity, ...xs),
    x1 = Math.max(box ? box.x + box.width : -Infinity, ...xs);
  const y0 = Math.min(box?.y ?? Infinity, ...ys),
    y1 = Math.max(box ? box.y + box.height : -Infinity, ...ys);
  const padX = Math.max(4, (24 - (x1 - x0)) / 2),
    padY = Math.max(4, (24 - (y1 - y0)) / 2);
  return { x: x0 - padX, y: y0 - padY, width: x1 - x0 + 2 * padX, height: y1 - y0 + 2 * padY };
}

/** The text next to an element: "R_1 = 100 Ω", "A_1", or a net label's name. */
function label_(e: ElementData): string {
  const unit = kindInfo(e.kind)?.unit ?? "";
  if (e.kind === "label" || e.kind === "port") return e.text ?? "";
  if (!isComponent(e.kind)) return "";
  if (e.kind === "button" && e.text) return `${e.id} [${keyLabel(e.text)}]`; // held with that key while it runs
  if (!hasValue(e.kind)) return e.id;
  if (kindInfo(e.kind)?.meter && !e.value) return e.id; // no reading: the simulation fills it in
  const wave = isWaveSource(e.kind) ? `, ${waveLabel(e.text)}` : "";
  return `${e.id} = ${e.value ?? "?"}${e.value && /\d$/.test(e.value) ? ` ${unit}` : ""}${wave}`;
}

function Label({
  text,
  x,
  y,
  anchor,
  solved,
}: {
  text: string;
  x: number;
  y: number;
  anchor: "middle" | "end" | "start";
  solved?: boolean;
}) {
  const parts = text.match(/^([A-Za-z]+)_(\w+)(.*)$/);
  return (
    <text x={x} y={y} textAnchor={anchor} className={`label ${solved ? "solved" : ""}`}>
      {parts ? (
        <>
          {parts[1]}
          <tspan className="sub" dy="4">
            {parts[2]}
          </tspan>
          <tspan dy="-4">{parts[3]}</tspan>
        </>
      ) : (
        text
      )}
    </text>
  );
}

const ARROW: Record<number, [string, string]> = { 0: ["→", "←"], 90: ["↓", "↑"], 180: ["←", "→"], 270: ["↑", "↓"] };

/** A voltage's colour while running: towards green above ground, red below, the ink at 0 V. */
export const liveColor = (v: number | null, scale: number) =>
  v === null
    ? undefined
    : `color-mix(in oklab, ${v >= 0 ? "var(--live-pos)" : "var(--live-neg)"} ${Math.round(Math.min(1, Math.abs(v) / scale) * 100)}%, var(--live-zero))`;

/**
 * The leads of an element with more than two pins (symbol px, before rotation): from each pin
 * along its lead into the body, so each takes its own node's colour. A chip's pins sit on its
 * box's edges, 20 px of lead each; the others are listed.
 */
function leads(kind: string, symbolPins: number[][]): number[][] {
  if (kind === "npn" || kind === "pnp")
    return [
      [30, 0],
      [0, 18],
      [0, -18],
    ];
  if (kind === "nmos" || kind === "pmos")
    return [
      [22, 0],
      [0, 28],
      [0, -28],
    ];
  if (kind === "opamp")
    return [
      [20, 0],
      [20, 0],
      [-20, 0],
    ];
  if (kind === "vcvs" || kind === "vccs")
    return [
      [14, 0],
      [14, 0],
      [0, -24],
      [0, 24],
    ];
  if (kind === "transformer")
    return [
      [24, 0],
      [24, 0],
      [-24, 0],
      [-24, 0],
    ];
  if (kind === "ccvs" || kind === "cccs")
    return [
      [0, 40],
      [0, -40],
      [0, -24],
      [0, 24],
    ];
  if (kind === "potentiometer")
    return [
      [0, 0],
      [0, 0],
      [0, 27],
    ]; // its ends: the body's gradient
  if (kind === "dff" || kind === "jkff" || kind === "counter")
    return symbolPins.map(([x]) => (x === 0 ? [16, 0] : [-16, 0]));
  const xs = symbolPins.map((p) => p[0]),
    ys = symbolPins.map((p) => p[1]);
  return symbolPins.map(([x, y]) =>
    y === Math.min(...ys) ? [0, 20] : y === Math.max(...ys) ? [0, -20] : x === Math.min(...xs) ? [20, 0] : [-20, 0],
  );
}

type Props = {
  element: ElementData;
  library: SymbolLibrary;
  wires: WireData[];
  result?: ElementResult;
  selected: boolean;
  closed?: boolean; // a switch or a button: drawn closed
  lit?: number; // an LED while simulating: how bright (0–1)
  look?: Record<string, number>; // while simulating, what else it shows: its symbol's CSS variables (--a, --angle, …)
  live?: { pins: (number | null)[]; scale: number }; // running: its pins' voltages, the element coloured by them
  onPointerDown: (event: ReactPointerEvent, element: ElementData) => void;
};

const sameResult = (a?: ElementResult, b?: ElementResult) =>
  a === b ||
  (!!a &&
    !!b &&
    a.value === b.value &&
    a.solved === b.solved &&
    a.U === b.U &&
    a.I === b.I &&
    a.P === b.P &&
    a.reversed === b.reversed);
// a glow to the percent, an angle to the degree: finer is not seen
const sameLook = (a?: Record<string, number>, b?: Record<string, number>) =>
  a === b ||
  (!!a &&
    !!b &&
    Object.keys(a).length === Object.keys(b).length &&
    Object.keys(a).every((k) => Math.round(a[k] * 100) === Math.round((b[k] ?? NaN) * 100)));
const sameColours = (a: Props["live"], b: Props["live"]) =>
  a === b ||
  (!!a &&
    !!b &&
    a.pins.length === b.pins.length &&
    a.pins.every((v, i) => liveColor(v, a.scale) === liveColor(b.pins[i], b.scale)));

/**
 * Drawn again only when what it shows changed: while the circuit runs, the board gets new numbers
 * 30 times a second, and most elements look just as they did (the same colours, the same readings).
 */
export const ElementView = memo(
  ElementView_,
  (a, b) =>
    a.element === b.element &&
    a.library === b.library &&
    a.wires === b.wires &&
    a.selected === b.selected &&
    a.closed === b.closed &&
    (a.lit ?? 0) > 0.01 === (b.lit ?? 0) > 0.01 &&
    a.onPointerDown === b.onPointerDown &&
    sameResult(a.result, b.result) &&
    sameColours(a.live, b.live) &&
    sameLook(a.look, b.look),
);

function ElementView_({ element: e, library, wires, result, selected, closed, lit, look, live, onPointerDown }: Props) {
  const G = library.grid;
  const symbol = symbolOf(e, library);
  const ps = pins(e, library).map(([x, y]) => [x * G, y * G] as Point);
  const gradient = useId(); // unique on the page: other boards have their R_1 too
  // the symbol as drawn, measured (symbols differ, and rotate): what grabs it, and its frame when selected
  const body = useRef<SVGGElement>(null);
  const [box, setBox] = useState<DOMRect | null>(null);
  useLayoutEffect(() => {
    const measured = body.current?.getBBox?.();
    setBox(measured && (measured.width || measured.height) ? measured : null); // (a net label draws nothing: 0 × 0 at the origin)
  }, [e.at[0], e.at[1], e.rotation, e.kind, symbol.svg]);
  const frame = selected ? box : null;
  // running: a two-pin element (and a potentiometer's body) shades from one pin's colour to the
  // other's, so it reads as the wires on both sides do; longer leads get a colour each
  const colours = live?.pins.map((v) => liveColor(v, live.scale));
  const shaded = colours && (ps.length === 2 || e.kind === "potentiometer") && colours[0] && colours[1];
  const tinted = shaded
    ? { stroke: `url(#${CSS.escape(gradient)})`, color: `color-mix(in oklab, ${colours[0]}, ${colours[1]})` }
    : undefined;
  const ownLeads =
    colours &&
    (ps.length > 3 ||
      e.kind === "potentiometer" ||
      e.kind === "npn" ||
      e.kind === "pnp" ||
      e.kind === "nmos" ||
      e.kind === "pmos" ||
      e.kind === "opamp" ||
      e.kind === "part")
      ? (symbol.leads ?? leads(e.kind, symbol.pins))
          .map(([dx, dy], i) => {
            const [rx, ry] = rotate([dx, dy], symbol.upright ? 0 : e.rotation);
            return { from: ps[i], to: [ps[i][0] + rx, ps[i][1] + ry] as Point, colour: colours[i] };
          })
          .filter((l) => l.colour && (l.to[0] !== l.from[0] || l.to[1] !== l.from[1]))
      : [];
  const cx = ps.reduce((s, p) => s + p[0], 0) / ps.length;
  const cy = ps.reduce((s, p) => s + p[1], 0) / ps.length;
  const xs = ps.map((p) => p[0]);
  const ys = ps.map((p) => p[1]);
  const vertical = e.rotation % 180 !== 0;
  // label left of a vertical element (above a horizontal one), unless a wire runs through there
  const labelWidth = 7.4 * label_(e).replace("_", "").length + 6;
  const crosses = (x0: number, x1: number, y0: number, y1: number) =>
    wires.some((w) =>
      w.points.slice(1).some((q, i) => {
        const [ax, ay] = [w.points[i][0] * G, w.points[i][1] * G];
        const [bx, by] = [q[0] * G, q[1] * G];
        return Math.min(ax, bx) <= x1 && Math.max(ax, bx) >= x0 && Math.min(ay, by) <= y1 && Math.max(ay, by) >= y0;
      }),
    );
  // …and always when it would not fit on the canvas (which starts at 0, 0): cut-off text is
  // worse than text over a wire (the text has a halo)
  const flip = vertical
    ? cx - 20 - labelWidth < 0 ||
      (crosses(cx - 20 - labelWidth, cx - 20, cy - 8, cy + 8) &&
        !crosses(cx + 20, cx + 20 + labelWidth, cy - 8, cy + 8))
    : cy - 32 < 0 ||
      (crosses(cx - labelWidth / 2, cx + labelWidth / 2, cy - 32, cy - 16) &&
        !crosses(cx - labelWidth / 2, cx + labelWidth / 2, cy + 16, cy + 32));
  // a 555, an Arduino, a display: the label beside the box, top right; no readings (its pins tell)
  const chip = kindInfo(e.kind)?.group === "chips" || ps.length > 4 || e.kind === "part";
  const vars =
    look &&
    (Object.fromEntries(Object.entries(look).map(([k, v]) => [`--${k}`, Math.round(v * 100) / 100])) as CSSProperties);
  const label =
    result?.solved && result.value
      ? e.kind === "hole"
        ? `${e.id}: ${result.value}`
        : isBoard(e.kind)
          ? `${e.id} · ${result.value}`
          : `${e.id} = ${result.value}` // (a board: its clock, slowed)
      : label_(e);
  const readings =
    result && !chip
      ? ([
          result.I && `I = ${result.I} ${ARROW[e.rotation][result.reversed ? 1 : 0]}`,
          result.U && `U = ${result.U}`,
        ].filter(Boolean) as string[])
      : [];
  return (
    <g
      className={`element ${selected ? "selected" : ""} ${closed ? "closed" : ""} ${lit && lit > 0.01 ? "lit" : ""}`}
      data-id={e.id}
      data-kind={e.kind}
      style={vars}
      onPointerDown={(event) => onPointerDown(event, e)}
    >
      <rect className="hit" {...hitArea(box, xs, ys)} />
      {shaded && (
        <linearGradient
          id={gradient}
          gradientUnits="userSpaceOnUse"
          x1={ps[0][0]}
          y1={ps[0][1]}
          x2={ps[1][0]}
          y2={ps[1][1]}
        >
          <stop offset="0.2" style={{ stopColor: colours[0] }} />
          <stop offset="0.8" style={{ stopColor: colours[1] }} />
        </linearGradient>
      )}
      {frame && (
        <rect
          className="frame"
          x={frame.x - 6}
          y={frame.y - 6}
          width={frame.width + 12}
          height={frame.height + 12}
          rx="4"
        />
      )}
      <g ref={body}>
        <g
          className="w"
          transform={`translate(${e.at[0] * G} ${e.at[1] * G}) rotate(${symbol.upright ? 0 : e.rotation})`}
          style={tinted}
          dangerouslySetInnerHTML={{ __html: symbol.svg }}
        />
      </g>
      {ownLeads.map((l, i) => (
        <path
          key={i}
          className="lead"
          d={`M${l.from[0]} ${l.from[1]}L${l.to[0]} ${l.to[1]}`}
          style={{ stroke: l.colour }}
        />
      ))}
      {symbol.letter && (
        <text className="letter" x={cx} y={cy}>
          {symbol.letter}
        </text>
      )}
      {label &&
        (e.kind === "label" || e.kind === "port" ? (
          <text x={e.kind === "port" ? cx + 8 : cx + 4} y={e.kind === "port" ? cy - 9 : cy - 6} className="node">
            {label}
          </text>
        ) : symbol.box && e.rotation === 0 ? (
          // one's own component: beside its box, top right (past a lead on its right)
          <Label
            text={label}
            x={Math.max(e.at[0] * G + symbol.box[0], ...xs) + 8}
            y={e.at[1] * G + 12}
            anchor="start"
          />
        ) : chip ? (
          <Label
            text={label}
            x={Math.max(...xs) + 8}
            y={Math.min(...ys) + (e.kind === "arduino" ? 44 : 24)}
            anchor="start"
          />
        ) : vertical ? (
          <Label
            text={label}
            x={flip ? cx + 20 : cx - 20}
            y={readings.length ? cy - 2 : cy + 4}
            anchor={flip ? "start" : "end"}
            solved={result?.solved}
          />
        ) : (
          <Label text={label} x={cx} y={flip ? cy + 30 : cy - 20} anchor="middle" solved={result?.solved} />
        ))}
      {readings.map((text, i) =>
        vertical ? (
          // beside a vertical element: one block under its label, on the same (free) side
          <text
            key={i}
            className="reading"
            x={flip ? cx + 20 : cx - 20}
            y={cy + 19 + i * 14}
            textAnchor={flip ? "start" : "end"}
          >
            {text}
          </text>
        ) : (
          <text key={i} className="reading" x={cx} y={(flip ? cy - 34 : cy + 28) + i * 14} textAnchor="middle">
            {text}
          </text>
        ),
      )}
    </g>
  );
}
