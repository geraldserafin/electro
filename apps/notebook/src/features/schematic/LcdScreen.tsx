// What an LCD shows while the circuit runs, drawn over its glass (the symbol's window: 6, 44,
// 288 × 74 px from its first pin): 16 × 2 cells, the ROM's characters as text, the custom glyphs
// dot by dot, the cursor; lit green when the backlight is on, the characters as dark as the contrast.

/** simulation/lcd.ts's Screen: what the controller shows. */
export interface LcdScreenData {
  lines: number[][]; // character codes (0–15: a glyph from CGRAM)
  text: string[][];
  cgram: number[];
  cursor: [number, number] | null;
  underline: boolean;
  blink: boolean;
  contrast: number;
  backlight: number;
}

const GLASS = { x: 6, y: 44, width: 288, height: 74 };
const CELL = { width: GLASS.width / 16, height: GLASS.height / 2 };
const DOT = 3; // px: a glyph's dot (5 × 8 of them in a cell)
const INK = "#1d2b10";

export function LcdScreen({ screen, at, rotation }: { screen: LcdScreenData; at: [number, number]; rotation: number }) {
  const lit = screen.backlight;
  // unlit it is a dull grey-green; lit, the familiar yellow-green
  const glass = `color-mix(in oklab, #b8e35a ${Math.round(lit * 100)}%, #72805a)`;
  const blinkOn = Math.floor(Date.now() / 400) % 2 === 0;
  const cell = (col: number, line: number) => [GLASS.x + col * CELL.width, GLASS.y + line * CELL.height] as const;
  return (
    <g className="lcd-screen" transform={`translate(${at[0]} ${at[1]}) rotate(${rotation})`}>
      <rect {...GLASS} rx="2" style={{ fill: glass }} />
      <g style={{ fill: INK, opacity: screen.contrast }}>
        {screen.lines.flatMap((line, row) => line.map((code, col) => {
          const [x, y] = cell(col, row);
          if (code < 16) { // a custom glyph: CGRAM's rows, 5 bits each (bit 4 on the left)
            const x0 = x + (CELL.width - 5 * DOT) / 2, y0 = y + (CELL.height - 8 * DOT) / 2;
            return screen.cgram.slice((code & 7) * 8, (code & 7) * 8 + 8).flatMap((bits, r) =>
              [0, 1, 2, 3, 4].filter((c) => bits & (0x10 >> c)).map((c) =>
                <rect key={`${row}.${col}.${r}.${c}`} x={x0 + c * DOT} y={y0 + r * DOT} width={DOT - 0.4} height={DOT - 0.4} />));
          }
          const char = screen.text[row][col];
          return char === " " ? [] : [
            <text key={`${row}.${col}`} x={x + CELL.width / 2} y={y + CELL.height / 2 + 8} textAnchor="middle">{char}</text>,
          ];
        }))}
        {screen.cursor && (() => {
          const [x, y] = cell(...screen.cursor);
          return (
            <>
              {screen.blink && blinkOn && <rect x={x + 1.5} y={y + 5} width={CELL.width - 3} height={CELL.height - 10} opacity={0.8} />}
              {screen.underline && <rect x={x + 2} y={y + CELL.height - 7} width={CELL.width - 4} height={2.5} />}
            </>
          );
        })()}
      </g>
    </g>
  );
}
