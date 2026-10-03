import { useLayoutEffect, useRef, useState } from "react";
import type { ElementResult, Point, SchematicData, SymbolLibrary } from "@/shared/model/types";
import { ElementView } from "./ElementView";
import { besides, inTheWay, junctions } from "./model";
import { withParts } from "./parts";
import "./Canvas.css";

const PDF_SCALE = 1.1; // drawing px → CSS px on paper: labels come out about as big as the text
const PDF_PAD = 6;

/**
 * The drawing for the PDF: cropped to what is drawn (texts included), no grid, no selection,
 * the same scale whatever the zoom on screen. Hidden on screen but laid out (not display:none),
 * so it can measure itself.
 */
const nothing = () => {};

export function PdfDrawing({
  value,
  library: symbols,
  results,
}: {
  value: SchematicData;
  library: SymbolLibrary;
  results?: Record<string, ElementResult>;
}) {
  const library = withParts(symbols, value.parts);
  const G = library.grid;
  const content = useRef<SVGGElement>(null);
  const [box, setBox] = useState<[number, number, number, number] | null>(null);
  useLayoutEffect(() => {
    const b = content.current?.getBBox();
    if (!b?.width) return;
    const next: [number, number, number, number] = [
      b.x - PDF_PAD,
      b.y - PDF_PAD,
      b.width + 2 * PDF_PAD,
      b.height + 2 * PDF_PAD,
    ];
    if (!box || next.some((v, i) => Math.abs(v - box[i]) > 0.5)) setBox(next);
  });
  if (!value.elements.length && !value.wires.length) return null;
  const obstacles = inTheWay(value, library);
  const aside = besides(value, library);
  const pointsOf = (ps: Point[]) => ps.map(([x, y]) => `${x * G},${y * G}`).join(" ");
  const [x, y, w, h] = box ?? [0, 0, 1, 1];
  return (
    <div className="pdf-drawing" aria-hidden>
      <svg className="canvas" viewBox={`${x} ${y} ${w} ${h}`} width={w * PDF_SCALE} height={h * PDF_SCALE}>
        <style>{library.style}</style>
        <g ref={content}>
          {value.wires.map((wire, i) => (
            <polyline key={i} className="w wire" points={pointsOf(wire.points)} />
          ))}
          {junctions(value, library).map(([jx, jy]) => (
            <circle key={`j${jx},${jy}`} className="dot" cx={jx * G} cy={jy * G} r="3" />
          ))}
          {value.elements.map((e) => (
            <ElementView
              key={e.id}
              element={e}
              library={library}
              wires={obstacles}
              result={results?.[e.id]}
              selected={false}
              aside={aside.has(e.id)}
              onPointerDown={nothing}
            />
          ))}
        </g>
      </svg>
    </div>
  );
}
