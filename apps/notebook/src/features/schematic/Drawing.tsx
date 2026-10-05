import type { ElementResult, Point, SchematicData, SymbolLibrary } from "@/shared/model/types";
import { ElementView } from "./ElementView";
import { besides, inTheWay, junctions } from "./model";

const nothing = () => {};

/** A drawing's wires, junctions and elements as they are, nothing to click: for the PDF and for pictures. */
export function Drawing({
  value,
  library,
  results,
}: {
  value: SchematicData;
  library: SymbolLibrary; // with the drawing's own parts
  results?: Record<string, ElementResult>;
}) {
  const G = library.grid;
  const obstacles = inTheWay(value, library);
  const aside = besides(value, library);
  const pointsOf = (ps: Point[]) => ps.map(([x, y]) => `${x * G},${y * G}`).join(" ");
  return (
    <>
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
    </>
  );
}
