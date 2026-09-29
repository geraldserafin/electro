// One element on the drawing: its symbol, its label ("R_1 = 100 Ω", beside it where no wire runs),
// and after a run what was found (the solved value, I and U).
import { useId, useLayoutEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import type { ElementData, ElementResult, Point, SymbolLibrary, WireData } from "@/shared/model/types";
import { hasValue, isComponent, kindInfo, pins, rotate } from "./model";

/** The text next to an element: "R_1 = 100 Ω", "A_1", or a net label's name. */
function label_(e: ElementData): string {
  const unit = kindInfo(e.kind)?.unit ?? "";
  if (e.kind === "label") return e.text ?? "";
  if (!isComponent(e.kind)) return "";
  if (!hasValue(e.kind)) return e.id;
  if (kindInfo(e.kind)?.meter && !e.value) return e.id; // no reading: the simulation fills it in
  return `${e.id} = ${e.value ?? "?"}${e.value && /\d$/.test(e.value) ? ` ${unit}` : ""}`;
}

function Label({ text, x, y, anchor, solved }: {
  text: string; x: number; y: number; anchor: "middle" | "end" | "start"; solved?: boolean;
}) {
  const parts = text.match(/^([A-Za-z]+)_(\w+)(.*)$/);
  return (
    <text x={x} y={y} textAnchor={anchor} className={`label ${solved ? "solved" : ""}`}>
      {parts ? (
        <>
          {parts[1]}
          <tspan className="sub" dy="4">{parts[2]}</tspan>
          <tspan dy="-4">{parts[3]}</tspan>
        </>
      ) : text}
    </text>
  );
}

const ARROW: Record<number, [string, string]> = { 0: ["→", "←"], 90: ["↓", "↑"], 180: ["←", "→"], 270: ["↑", "↓"] };

/** A voltage's colour while running: towards green above ground, red below, the ink at 0 V. */
export const liveColor = (v: number | null, scale: number) =>
  v === null ? undefined
    : `color-mix(in oklab, ${v >= 0 ? "var(--live-pos)" : "var(--live-neg)"} ${Math.round(Math.min(1, Math.abs(v) / scale) * 100)}%, var(--live-zero))`;

/**
 * The leads of an element with more than two pins (symbol px, before rotation): from each pin
 * along its lead into the body, so each takes its own node's colour. A chip's pins sit on its
 * box's edges, 20 px of lead each; the others are listed.
 */
function leads(kind: string, symbolPins: number[][]): number[][] {
  if (kind === "npn" || kind === "pnp") return [[30, 0], [0, 18], [0, -18]];
  if (kind === "opamp") return [[20, 0], [20, 0], [-20, 0]];
  if (kind === "potentiometer") return [[0, 0], [0, 0], [0, 27]]; // its ends: the body's gradient
  const xs = symbolPins.map((p) => p[0]), ys = symbolPins.map((p) => p[1]);
  return symbolPins.map(([x, y]) =>
    y === Math.min(...ys) ? [0, 20] : y === Math.max(...ys) ? [0, -20] : x === Math.min(...xs) ? [20, 0] : [-20, 0]);
}

export function ElementView({ element: e, library, wires, result, selected, closed, lit, live, onPointerDown }: {
  element: ElementData; library: SymbolLibrary; wires: WireData[]; result?: ElementResult; selected: boolean;
  closed?: boolean; // a switch or a button: drawn closed
  lit?: number; // an LED while simulating: how bright (0–1)
  live?: { pins: (number | null)[]; scale: number }; // running: its pins' voltages, the element coloured by them
  onPointerDown: (event: ReactPointerEvent) => void;
}) {
  const G = library.grid;
  const symbol = library.kinds[e.kind];
  const ps = pins(e, library).map(([x, y]) => [x * G, y * G] as Point);
  const gradient = useId(); // unique on the page: other boards have their R_1 too
  // selected: a frame around the symbol as drawn (measured — symbols differ, and rotate)
  const body = useRef<SVGGElement>(null);
  const [frame, setFrame] = useState<DOMRect | null>(null);
  useLayoutEffect(() => {
    setFrame(selected && body.current ? body.current.getBBox() : null);
  }, [selected, e.at[0], e.at[1], e.rotation, e.kind, symbol.svg]);
  // running: a two-pin element (and a potentiometer's body) shades from one pin's colour to the
  // other's, so it reads as the wires on both sides do; longer leads get a colour each
  const colours = live?.pins.map((v) => liveColor(v, live.scale));
  const shaded = colours && (ps.length === 2 || e.kind === "potentiometer") && colours[0] && colours[1];
  const tinted = shaded ? { stroke: `url(#${CSS.escape(gradient)})`, color: `color-mix(in oklab, ${colours[0]}, ${colours[1]})` } : undefined;
  const ownLeads = colours && (ps.length > 3 || e.kind === "potentiometer" || e.kind === "npn" || e.kind === "pnp" || e.kind === "opamp")
    ? leads(e.kind, symbol.pins).map(([dx, dy], i) => {
      const [rx, ry] = rotate([dx, dy], symbol.upright ? 0 : e.rotation);
      return { from: ps[i], to: [ps[i][0] + rx, ps[i][1] + ry] as Point, colour: colours[i] };
    }).filter((l) => l.colour && (l.to[0] !== l.from[0] || l.to[1] !== l.from[1]))
    : [];
  const cx = ps.reduce((s, p) => s + p[0], 0) / ps.length;
  const cy = ps.reduce((s, p) => s + p[1], 0) / ps.length;
  const xs = ps.map((p) => p[0]);
  const ys = ps.map((p) => p[1]);
  const vertical = e.rotation % 180 !== 0;
  // label left of a vertical element (above a horizontal one), unless a wire runs through there
  const labelWidth = 7.4 * (label_(e).replace("_", "").length) + 6;
  const crosses = (x0: number, x1: number, y0: number, y1: number) =>
    wires.some((w) => w.points.slice(1).some((q, i) => {
      const [ax, ay] = [w.points[i][0] * G, w.points[i][1] * G];
      const [bx, by] = [q[0] * G, q[1] * G];
      return Math.min(ax, bx) <= x1 && Math.max(ax, bx) >= x0 && Math.min(ay, by) <= y1 && Math.max(ay, by) >= y0;
    }));
  // …and always when it would not fit on the canvas (which starts at 0, 0): cut-off text is
  // worse than text over a wire (the text has a halo)
  const flip = vertical
    ? cx - 20 - labelWidth < 0
      || (crosses(cx - 20 - labelWidth, cx - 20, cy - 8, cy + 8) && !crosses(cx + 20, cx + 20 + labelWidth, cy - 8, cy + 8))
    : cy - 32 < 0
      || (crosses(cx - labelWidth / 2, cx + labelWidth / 2, cy - 32, cy - 16) && !crosses(cx - labelWidth / 2, cx + labelWidth / 2, cy + 16, cy + 32));
  const chip = ps.length > 3; // a 555, an Arduino: the label beside the box, top right; no readings (its pins tell)
  const label = result?.solved && result.value
    ? (e.kind === "hole" ? `${e.id}: ${result.value}` : `${e.id} = ${result.value}`)
    : label_(e);
  const readings = result && !chip
    ? [result.I && `I = ${result.I} ${ARROW[e.rotation][result.reversed ? 1 : 0]}`, result.U && `U = ${result.U}`].filter(Boolean) as string[]
    : [];
  return (
    <g className={`element ${selected ? "selected" : ""} ${closed ? "closed" : ""} ${lit && lit > 0.01 ? "lit" : ""}`}
       data-id={e.id} data-kind={e.kind} onPointerDown={onPointerDown}>
      <rect
        className="hit"
        x={Math.min(...xs) - 12} y={Math.min(...ys) - 12}
        width={Math.max(...xs) - Math.min(...xs) + 24} height={Math.max(...ys) - Math.min(...ys) + 24}
      />
      {shaded && (
        <linearGradient id={gradient} gradientUnits="userSpaceOnUse" x1={ps[0][0]} y1={ps[0][1]} x2={ps[1][0]} y2={ps[1][1]}>
          <stop offset="0.2" style={{ stopColor: colours[0] }} />
          <stop offset="0.8" style={{ stopColor: colours[1] }} />
        </linearGradient>
      )}
      {frame && <rect className="frame" x={frame.x - 6} y={frame.y - 6} width={frame.width + 12} height={frame.height + 12} rx="4" />}
      <g ref={body}>
        <g className="w" transform={`translate(${e.at[0] * G} ${e.at[1] * G}) rotate(${symbol.upright ? 0 : e.rotation})`}
           style={tinted} dangerouslySetInnerHTML={{ __html: symbol.svg }} />
      </g>
      {ownLeads.map((l, i) => (
        <path key={i} className="lead" d={`M${l.from[0]} ${l.from[1]}L${l.to[0]} ${l.to[1]}`} style={{ stroke: l.colour }} />
      ))}
      {symbol.letter && <text className="letter" x={cx} y={cy}>{symbol.letter}</text>}
      {label && (e.kind === "label"
        ? <text x={cx + 4} y={cy - 6} className="node">{label}</text>
        : chip
          ? <Label text={label} x={Math.max(...xs) + 8} y={Math.min(...ys) + (e.kind === "arduino" ? 44 : 24)} anchor="start" />
        : vertical
          ? <Label text={label} x={flip ? cx + 20 : cx - 20} y={readings.length ? cy - 2 : cy + 4} anchor={flip ? "start" : "end"} solved={result?.solved} />
          : <Label text={label} x={cx} y={flip ? cy + 30 : cy - 20} anchor="middle" solved={result?.solved} />)}
      {readings.map((text, i) => vertical
        // beside a vertical element: one block under its label, on the same (free) side
        ? <text key={i} className="reading" x={flip ? cx + 20 : cx - 20} y={cy + 19 + i * 14}
                textAnchor={flip ? "start" : "end"}>{text}</text>
        : <text key={i} className="reading" x={cx} y={(flip ? cy - 34 : cy + 28) + i * 14} textAnchor="middle">{text}</text>)}
    </g>
  );
}
