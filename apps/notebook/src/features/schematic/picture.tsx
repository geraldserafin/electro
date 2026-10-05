import type { ElementResult, SchematicData, SymbolLibrary } from "@/shared/model/types";
import { Drawing } from "./Drawing";
import { bounds } from "./model";
import { withParts } from "./parts";

const PAD = 4; // grid units round what is drawn: room for the texts beside it

/** A drawing as a picture (SVG, its styles in it), with what was found on it (``results``). */
export async function pictureOf(
  sch: SchematicData,
  lib: SymbolLibrary,
  results?: Record<string, ElementResult>,
): Promise<string> {
  const { renderToStaticMarkup } = await import("react-dom/server");
  const library = withParts(lib, sch.parts);
  const G = library.grid;
  const [x0, y0, x1, y1] = bounds(sch, library);
  const [w, h] = [(x1 - x0 + 2 * PAD) * G, (y1 - y0 + 2 * PAD) * G];
  return renderToStaticMarkup(
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox={`${(x0 - PAD) * G} ${(y0 - PAD) * G} ${w} ${h}`}
      width={w}
      height={h}
    >
      <style>{library.style}</style>
      <Drawing value={sch} library={library} results={results} />
    </svg>,
  );
}
