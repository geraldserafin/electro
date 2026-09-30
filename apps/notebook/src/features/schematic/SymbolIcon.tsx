import { useLayoutEffect, useRef, useState } from "react";
import { cn } from "@/shared/lib/cn";
import type { SymbolLibrary } from "@/shared/model/types";
import { isComponent } from "./model";

// what a symbol takes (px, at rotation 0: x, y, width, height), measured once it is drawn: symbols
// differ (a resistor, an Arduino), and a view box set by hand cuts the bigger ones off
const measured = new Map<string, string>();
const FIRST = "-6 -26 92 52"; // before it is measured: a two-pin one's

/** A kind's symbol, small: in the library, on the inspector, on the toolbar — all of it, as on the
 *  board (its letter too, the strokes as thick), fitted to its box (``box``: one's own component's
 *  view box). A node label, a port: a tag. */
export function SymbolIcon({
  kind,
  library,
  box,
  className,
}: {
  kind: string;
  library: SymbolLibrary;
  box?: string;
  className?: string;
}) {
  const symbol = library.kinds[kind];
  const svg = symbol?.svg ?? "";
  const drawn = useRef<SVGGElement>(null);
  const [fitted, setFitted] = useState(() => measured.get(svg));
  useLayoutEffect(() => {
    if (box || measured.has(svg)) return setFitted(measured.get(svg));
    const b = drawn.current?.getBBox?.();
    if (!b || !(b.width || b.height)) return;
    const pad = 3 + Math.max(b.width, b.height) * 0.02; // the strokes, and a little air
    const view = `${b.x - pad} ${b.y - pad} ${b.width + 2 * pad} ${b.height + 2 * pad}`;
    measured.set(svg, view);
    setFitted(view);
  }, [svg, box]);
  if (!isComponent(kind) && kind !== "ground")
    return (
      <svg viewBox="0 0 30 22" width="30" height="22" className={cn("flex-none text-fg", className)}>
        <path
          d="M4 11h5l4-5h13v10H13l-4-5"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinejoin="round"
        />
      </svg>
    );
  // the letter in its middle (an ammeter's A), as the board puts it
  const pins = symbol?.pins ?? [];
  const cx = pins.reduce((s, p) => s + p[0], 0) / (pins.length || 1);
  const cy = pins.reduce((s, p) => s + p[1], 0) / (pins.length || 1);
  return (
    <svg
      viewBox={box ?? fitted ?? FIRST}
      width="30"
      height="22"
      className={cn("symbol-icon flex-none text-fg", className)}
    >
      <g ref={drawn}>
        <g className="w" dangerouslySetInnerHTML={{ __html: svg }} />
        {symbol?.letter && (
          <text className="letter" x={cx} y={cy}>
            {symbol.letter}
          </text>
        )}
      </g>
    </svg>
  );
}
