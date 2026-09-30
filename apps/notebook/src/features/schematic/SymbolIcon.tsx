import type { SymbolLibrary } from "@/shared/model/types";
import { isComponent } from "./model";

// what a symbol takes, where it is not a two-pin one's (px, at rotation 0: x, y, width, height)
const BOXES: Record<string, string> = {
  ground: "-14 -4 28 26",
  relay: "-20 -12 160 104",
  not_gate: "-4 -22 88 44",
  and_gate: "-4 -16 88 72",
  nand_gate: "-4 -16 88 72",
  or_gate: "-4 -16 88 72",
  nor_gate: "-4 -16 88 72",
  xor_gate: "-4 -16 88 72",
};

/** A kind's symbol, small: in the library, on the inspector (``box``: its view box, for one's own
 *  components, which have their own sizes). A node label, a port: a tag. */
export function SymbolIcon({ kind, library, box }: { kind: string; library: SymbolLibrary; box?: string }) {
  if (isComponent(kind) || kind === "ground")
    return (
      <svg viewBox={box ?? BOXES[kind] ?? "-6 -26 92 52"} width="30" height="22" className="flex-none text-fg">
        <g className="w" dangerouslySetInnerHTML={{ __html: library.kinds[kind]?.svg ?? "" }} />
      </svg>
    );
  return (
    <svg viewBox="0 0 30 22" width="30" height="22" className="flex-none text-fg">
      <path d="M4 11h5l4-5h13v10H13l-4-5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
    </svg>
  );
}
