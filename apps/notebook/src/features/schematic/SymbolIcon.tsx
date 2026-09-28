import type { SymbolLibrary } from "@/shared/model/types";
import { isComponent } from "./model";

/** A kind's symbol, small: in the library, on the inspector. A node label: a tag. */
export function SymbolIcon({ kind, library }: { kind: string; library: SymbolLibrary }) {
  if (isComponent(kind) || kind === "ground")
    return (
      <svg viewBox={kind === "ground" ? "-14 -4 28 26" : "-6 -26 92 52"} width="30" height="22" className="flex-none text-fg">
        <g className="w" dangerouslySetInnerHTML={{ __html: library.kinds[kind].svg }} />
      </svg>
    );
  return (
    <svg viewBox="0 0 30 22" width="30" height="22" className="flex-none text-fg">
      <path d="M4 11h5l4-5h13v10H13l-4-5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
    </svg>
  );
}
