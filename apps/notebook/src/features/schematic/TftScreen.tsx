// What a 320×240 colour TFT shows while the circuit runs, over its glass (the symbol's: 66, −30 from its
// first pin, 1 px a pixel): the picture on a canvas, drawn as each new one comes (from the worker as it is
// drawn whole — Doom's up to 35 a second — not with the board's frames, nor through React); without the
// controller driving it the glass is blank — white where the backlight shines through (a TN panel's
// "normally white"), dark without it — and the backlight dims the whole.
import { useEffect, useRef } from "react";

/** Where a TFT's pictures come from (useLive's): ``draw`` gets the last one at once, then each new one (RGBA, 320 × 240), till the returned function is called. */
export interface TftPictures {
  watch(id: string, draw: (image: Uint8ClampedArray) => void): () => void;
}

/** simulation/tft.ts's TftData, as the board gets it, and its pictures. */
export interface TftScreenData {
  shown: boolean;
  backlight: number; // 0–1
  pictures: TftPictures;
}

const GLASS = { x: 66, y: -30 };
const WIDTH = 320, HEIGHT = 240;

export function TftScreen({ id, screen, at, rotation }: { id: string; screen: TftScreenData; at: [number, number]; rotation: number }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const { pictures } = screen;
  useEffect(() => {
    const c = canvas.current?.getContext("2d");
    if (!c) return;
    return pictures.watch(id, (image) => c.putImageData(new ImageData(image as Uint8ClampedArray<ArrayBuffer>, WIDTH, HEIGHT), 0, 0));
  }, [id, pictures]);
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
