// One element on the drawing: its symbol, its label ("R_1 = 100 Ω", beside it where no wire runs),
// and after a run what was found (the solved value, I and U).
import type { PointerEvent as ReactPointerEvent } from "react";
import type { ElementData, ElementResult, Point, SymbolLibrary, WireData } from "@/shared/model/types";
import { hasValue, isComponent, kindInfo, pins } from "./model";

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

export function ElementView({ element: e, library, wires, result, selected, onPointerDown }: {
  element: ElementData; library: SymbolLibrary; wires: WireData[]; result?: ElementResult; selected: boolean;
  onPointerDown: (event: ReactPointerEvent) => void;
}) {
  const G = library.grid;
  const symbol = library.kinds[e.kind];
  const ps = pins(e, library).map(([x, y]) => [x * G, y * G] as Point);
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
  const label = result?.solved && result.value
    ? (e.kind === "hole" ? `${e.id}: ${result.value}` : `${e.id} = ${result.value}`)
    : label_(e);
  const readings = result
    ? [result.I && `I = ${result.I} ${ARROW[e.rotation][result.reversed ? 1 : 0]}`, result.U && `U = ${result.U}`].filter(Boolean) as string[]
    : [];
  return (
    <g className={`element ${selected ? "selected" : ""}`} data-id={e.id} onPointerDown={onPointerDown}>
      <rect
        className="hit"
        x={Math.min(...xs) - 12} y={Math.min(...ys) - 12}
        width={Math.max(...xs) - Math.min(...xs) + 24} height={Math.max(...ys) - Math.min(...ys) + 24}
      />
      <g className="w" transform={`translate(${e.at[0] * G} ${e.at[1] * G}) rotate(${symbol.upright ? 0 : e.rotation})`}
         dangerouslySetInnerHTML={{ __html: symbol.svg }} />
      {symbol.letter && <text className="letter" x={cx} y={cy}>{symbol.letter}</text>}
      {label && (e.kind === "label"
        ? <text x={cx + 4} y={cy - 6} className="node">{label}</text>
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
