import type { SymbolLibrary } from "@/shared/model/types";
import symbols from "./symbols.json";

// generated from electro_render.symbol_library() (scripts/make_symbols.py), so drawings
// show before Python has loaded
export const library = symbols as unknown as SymbolLibrary;
