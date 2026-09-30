// One's own components on a drawing (kind "part", its text the key of its definition in the
// drawing's ``parts``): drawn as a box with its pins around it, the same as Python draws it
// (electro_render.symbols.part_symbol). The editor sees them through the symbol library: each
// definition is a kind of its own there, "part:<key>".
import type { ElementData, PartDef, PartPin, Point, SchematicData, SymbolLibrary } from "@/shared/model/types";

/** A part's kind in the symbol library. */
export const partKind = (key: string) => `part:${key}`;
/** Where an element's symbol is in the library: its kind, or for a part its definition's. */
export const symbolKey = (e: Pick<ElementData, "kind" | "text">) =>
  e.kind === "part" ? partKind(e.text ?? "") : e.kind;

/** Each pin's place, grid squares from the box's top left corner (the element's origin). */
export function offsets(def: PartDef): Point[] {
  const [w, h] = def.size;
  return def.pins.map(({ side, at }) =>
    side === "left" ? [-1, at] : side === "right" ? [w + 1, at] : side === "top" ? [at, -1] : [at, h + 1],
  );
}

const escapeXml = (text: string) =>
  text.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#x27;" })[c]!);

/** Its symbol: the box, a lead to each pin, the pins' names inside, its own name in the middle. */
export function partSvg(def: PartDef, G: number): string {
  const [w, h] = [def.size[0] * G, def.size[1] * G];
  const leads: string[] = [];
  const names: string[] = [];
  offsets(def).forEach(([px, py], i) => {
    const [x, y] = [px * G, py * G];
    const pin = def.pins[i];
    const name = escapeXml(pin.name);
    if (pin.side === "left") {
      leads.push(`M${x} ${y}H0`);
      names.push(`<text x="4" y="${y + 3}">${name}</text>`);
    } else if (pin.side === "right") {
      leads.push(`M${x} ${y}H${w}`);
      names.push(`<text x="${w - 4}" y="${y + 3}" text-anchor="end">${name}</text>`);
    } else if (pin.side === "top") {
      leads.push(`M${x} ${y}V0`);
      names.push(`<text x="${x}" y="11" text-anchor="middle">${name}</text>`);
    } else {
      leads.push(`M${x} ${y}V${h}`);
      names.push(`<text x="${x}" y="${h - 4}" text-anchor="middle">${name}</text>`);
    }
  });
  return (
    `<rect x="0" y="0" width="${w}" height="${h}" rx="3"/><path d="${leads.join("")}"/>` +
    `<g class="pins">${names.join("")}</g>` +
    `<text class="chip" x="${w / 2}" y="${h / 2 + 4}" text-anchor="middle">${escapeXml(def.name)}</text>`
  );
}

/** A part whose definition the drawing does not have: a dashed box with a question mark. */
const MISSING = {
  pins: [],
  svg: '<rect class="dashed" x="0" y="0" width="80" height="60" rx="3"/>',
  letter: "?",
  upright: false,
};

const cache = new WeakMap<SymbolLibrary, WeakMap<object, SymbolLibrary>>();

/** ``lib`` with the drawing's own components in it, each as the kind "part:<key>". */
export function withParts(lib: SymbolLibrary, parts: SchematicData["parts"]): SymbolLibrary {
  if (!parts || !Object.keys(parts).length) return lib;
  let byParts = cache.get(lib);
  if (!byParts) cache.set(lib, (byParts = new WeakMap()));
  let extended = byParts.get(parts);
  if (!extended) {
    const G = lib.grid;
    const kinds = { ...lib.kinds };
    for (const [key, def] of Object.entries(parts))
      kinds[partKind(key)] = {
        pins: offsets(def).map(([x, y]) => [x * G, y * G]),
        svg: partSvg(def, G),
        letter: null,
        upright: false,
        box: [def.size[0] * G, def.size[1] * G],
        leads: def.pins.map(({ side }) =>
          side === "left" ? [G, 0] : side === "right" ? [-G, 0] : side === "top" ? [0, G] : [0, -G],
        ),
      };
    byParts.set(parts, (extended = { ...lib, kinds }));
  }
  return extended;
}

/** An element's symbol (a part without its definition: a placeholder). */
export const symbolOf = (e: Pick<ElementData, "kind" | "text">, lib: SymbolLibrary) =>
  lib.kinds[symbolKey(e)] ?? MISSING;

/** A part's symbol's view box (px), for a small picture of it. */
export const partBox = (def: PartDef | undefined, G: number) =>
  def ? `${-G - 4} ${-G - 4} ${(def.size[0] + 2) * G + 8} ${(def.size[1] + 2) * G + 8}` : undefined;

/** The definitions the drawing's parts use, and none it no longer does (undefined: none at all). */
export function usedParts(sch: SchematicData): SchematicData["parts"] {
  const used = new Set(sch.elements.filter((e) => e.kind === "part").map((e) => e.text ?? ""));
  const kept = Object.entries(sch.parts ?? {}).filter(([key]) => used.has(key));
  return kept.length ? Object.fromEntries(kept) : undefined;
}

/** The drawing's ports, by name, in the order a box would have them: left to right, top to bottom. */
export const ports = (sch: SchematicData) =>
  sch.elements
    .filter((e) => e.kind === "port" && (e.text ?? "").trim())
    .sort((a, b) => a.at[1] - b.at[1] || a.at[0] - b.at[0]);

/** Which side of a box each of the drawing's ports goes on at first: those on the drawing's left half
 *  on the left, the rest on the right, in their order from the top (one pin a name). */
export function firstSides(sch: SchematicData): { name: string; side: PartPin["side"] }[] {
  const found = ports(sch);
  const xs = found.map((e) => e.at[0]);
  const middle = (Math.min(...xs) + Math.max(...xs)) / 2;
  const seen = new Set<string>();
  return found.flatMap((e) => {
    const name = e.text!.trim();
    if (seen.has(name)) return [];
    seen.add(name);
    return [{ name, side: found.length > 1 && e.at[0] > middle ? ("right" as const) : ("left" as const) }];
  });
}

/** The box for pins on their sides, in their order: two squares apart, the box as big as they (and the
 *  names: about a third of a square a letter) need, and `more` squares wider and taller. */
export function arrange(
  sides: { name: string; side: PartPin["side"] }[],
  name: string,
  more: [number, number] = [0, 0],
): Pick<PartDef, "size" | "pins"> {
  const on = (side: PartPin["side"]) => sides.filter((p) => p.side === side);
  const longest = (side: PartPin["side"]) => Math.max(0, ...on(side).map((p) => p.name.length));
  const rows = Math.max(on("left").length, on("right").length, 1);
  const cols = Math.max(on("top").length, on("bottom").length, 0);
  const text = Math.ceil((longest("left") + longest("right") + name.length / 1.5) / 3) + 2;
  const even = (n: number) => n + (n % 2);
  const width = even(Math.max(4, text, cols * 2 + 2) + more[0]);
  const height = even(Math.max(2, rows * 2 + (cols ? 2 : 0)) + more[1]);
  return {
    size: [width, height],
    pins: (["left", "right", "top", "bottom"] as const).flatMap((side) => {
      const these = on(side);
      const length = side === "left" || side === "right" ? height : width;
      // two squares apart, the row in the middle of its side
      return these.map((p, i) => ({ name: p.name, side, at: length / 2 - (these.length - 1) + 2 * i }));
    }),
  };
}
