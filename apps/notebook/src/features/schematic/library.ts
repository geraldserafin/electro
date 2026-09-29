import type { SymbolLibrary, SymbolStandard } from "@/shared/model/types";
import symbols from "./symbols.json";

// generated from electro_render.symbol_library() (scripts/make_symbols.py), so drawings
// show before Python has loaded
export const library = symbols as unknown as SymbolLibrary;

const byStandard = new Map<SymbolStandard, SymbolLibrary>();

/** The library drawing with ``standard``'s symbols (IEC's where it has none of its own). */
export function libraryFor(standard: SymbolStandard = "iec"): SymbolLibrary {
  let lib = byStandard.get(standard);
  if (!lib) {
    const own = library.standards?.[standard] ?? {};
    lib = { ...library, kinds: Object.fromEntries(Object.entries(library.kinds).map(([kind, k]) => [kind, own[kind] ? { ...k, svg: own[kind] } : k])) };
    byStandard.set(standard, lib);
  }
  return lib;
}
