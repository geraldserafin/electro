// What an LCD shows while the circuit runs, drawn over its glass (the symbol's window: 6, 44,
// 288 × 74 px from its first pin) as the real one looks: 16 × 2 cells of 5 × 8 dots, the characters
// from the controller's ROM (lcdFont.ts) or its CGRAM, the dots that are off faintly there too;
// the glass lit yellow-green by the backlight (grey without it), the dots as dark as the contrast
// lets them — and with too much of it, every dot darkens into the familiar boxes.
import { useId, useMemo } from "react";
import { ROM } from "./lcdFont";

/** simulation/lcd.ts's Screen: what the controller shows. */
export interface LcdScreenData {
  lines: number[][]; // character codes (0–15: a glyph from CGRAM)
  text: string[][];
  cgram: number[];
  cursor: [number, number] | null;
  underline: boolean;
  blink: boolean;
  contrast: number; // 0 (unreadable) – 1
  over: number; // 0 – 1: too much contrast, the dots that are off darken
  backlight: number; // 0–1
}

const GLASS = { x: 6, y: 44, width: 288, height: 74 };
const P = 2.8, DOT = 2.35; // px: from dot to dot, a dot's size
const CELL = { width: 6 * P, height: 10 * P }; // 5 × 8 dots, a dot's gap after a character, two after a line
const LEFT = GLASS.x + (GLASS.width - (16 * CELL.width - P)) / 2;
const TOP = GLASS.y + (GLASS.height - (2 * CELL.height - 2 * P)) / 2;

/** The dots of a cell that are on: 8 rows of 5 bits (bit 4 on the left). */
function cellRows(screen: LcdScreenData, code: number, col: number, line: number, blinkOn: boolean): number[] {
  const rows = code < 16
    ? screen.cgram.slice((code & 7) * 8, (code & 7) * 8 + 8)
    : Array.from(ROM.subarray(code * 8, code * 8 + 8));
  const here = screen.cursor && screen.cursor[0] === col && screen.cursor[1] === line;
  if (here && screen.blink && blinkOn) return rows.map(() => 0b11111);
  if (here && screen.underline) rows[7] = 0b11111;
  return rows;
}

export function LcdScreen({ screen, at, rotation, offset = [0, 0] }: {
  screen: LcdScreenData; at: [number, number]; rotation: number;
  offset?: [number, number]; // where the glass is unlike the parallel module's (the I²C one: 50 px right, 50 up)
}) {
  const dots = `lcd-dots${useId().replace(/[^\w-]/g, "")}`; // (useId's colons would need escaping in url(#…))
  const blinkOn = Math.floor(Date.now() / 400) % 2 === 0;
  // every dot that is on, as one path (made again only when what is on changes)
  const key = `${screen.lines.map((l) => l.join(",")).join(";")}|${screen.cgram.join(",")}|${screen.cursor}|${screen.underline}|${screen.blink && blinkOn}`;
  const lit = useMemo(() => {
    let d = "";
    screen.lines.forEach((codes, line) => codes.forEach((code, col) => {
      const x0 = LEFT + col * CELL.width, y0 = TOP + line * CELL.height;
      cellRows(screen, code, col, line, blinkOn).forEach((bits, r) => {
        for (let c = 0; c < 5; c++) if (bits & (0x10 >> c)) d += `M${(x0 + c * P).toFixed(1)} ${(y0 + r * P).toFixed(1)}h${DOT}v${DOT}h-${DOT}z`;
      });
    }));
    return d;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  const glass = `color-mix(in oklab, #b3dc4a ${Math.round(screen.backlight * 100)}%, #6f7c57)`;
  return (
    <g className="lcd-screen" transform={`translate(${at[0]} ${at[1]}) rotate(${rotation}) translate(${offset[0]} ${offset[1]})`}>
      <defs>
        <pattern id={dots} patternUnits="userSpaceOnUse" x={LEFT} y={TOP} width={P} height={P}>
          <rect width={DOT} height={DOT} fill="#18280a" />
        </pattern>
      </defs>
      <rect {...GLASS} rx="2" style={{ fill: glass }} />
      {/* the cells' dots that are off: a faint grid, darker with too much contrast */}
      <g opacity={0.05 + 0.55 * screen.over}>
        {[0, 1].flatMap((line) => Array.from({ length: 16 }, (_, col) => (
          <rect key={`${line}.${col}`} x={LEFT + col * CELL.width} y={TOP + line * CELL.height} width={5 * P} height={8 * P}
                fill={`url(#${dots})`} />
        )))}
      </g>
      <path d={lit} style={{ fill: "#18280a", opacity: Math.min(1, screen.contrast * 0.92) }} />
    </g>
  );
}
