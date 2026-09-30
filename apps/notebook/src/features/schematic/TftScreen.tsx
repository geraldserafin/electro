// What a 320×240 colour TFT shows while the circuit runs, over its glass (the symbol's: 66, −30 from its
// first pin, 1 px a pixel): the picture on a canvas, drawn again only when a new one comes; without the
// controller driving it the glass is blank — white where the backlight shines through (a TN panel's
// "normally white"), dark without it — and the backlight dims the whole.
import { useEffect, useRef } from "react";

/** simulation/tft.ts's TftData, as the board gets it. */
export interface TftScreenData {
  image: Uint8ClampedArray | null; // RGBA, 320 × 240; null: as last drawn
  shown: boolean;
  backlight: number; // 0–1
}

const GLASS = { x: 66, y: -30 };
const WIDTH = 320, HEIGHT = 240;

export function TftScreen({ screen, at, rotation }: { screen: TftScreenData; at: [number, number]; rotation: number }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const c = canvas.current?.getContext("2d");
    if (c && screen.image) c.putImageData(new ImageData(new Uint8ClampedArray(screen.image), WIDTH, HEIGHT), 0, 0);
  }, [screen.image]);
  const light = screen.backlight;
  return (
    <g className="tft-screen" transform={`translate(${at[0]} ${at[1]}) rotate(${rotation}) translate(${GLASS.x} ${GLASS.y})`}>
      <rect width={WIDTH} height={HEIGHT} style={{ fill: "#07090b" }} />
      {!screen.shown && light > 0 && <rect width={WIDTH} height={HEIGHT} style={{ fill: "#eef1f4", opacity: light }} />}
      <foreignObject width={WIDTH} height={HEIGHT} style={{ display: screen.shown ? undefined : "none", opacity: 0.08 + 0.92 * light }}>
        <canvas ref={canvas} width={WIDTH} height={HEIGHT} style={{ display: "block", width: WIDTH, height: HEIGHT, imageRendering: "pixelated" }} />
      </foreignObject>
    </g>
  );
}
