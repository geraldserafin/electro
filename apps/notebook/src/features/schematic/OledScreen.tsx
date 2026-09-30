// What a 128×64 OLED shows while the circuit runs, over its glass (the symbol's: −66, 44 from its
// first pin, 1.5 px a pixel): black glass, the lit pixels as one path, a row's run of them one rectangle.

/** simulation/i2c.ts's Pixels, as the board gets them: the lit runs already a path (in pixels). */
export interface OledScreenData {
  path: string; // "M x y h n v 1 h −n z" per run of lit pixels
  on: boolean;
  contrast: number; // 0–1
}

const GLASS = { x: -66, y: 44 };
const PIXEL = 1.5;

export function OledScreen({
  screen,
  at,
  rotation,
}: {
  screen: OledScreenData;
  at: [number, number];
  rotation: number;
}) {
  return (
    <g
      className="oled-screen"
      transform={`translate(${at[0]} ${at[1]}) rotate(${rotation}) translate(${GLASS.x} ${GLASS.y}) scale(${PIXEL})`}
    >
      <rect width="128" height="64" style={{ fill: "#0a0f14" }} />
      {screen.on && <path d={screen.path} style={{ fill: "#8fe3ff", opacity: screen.contrast }} />}
    </g>
  );
}
