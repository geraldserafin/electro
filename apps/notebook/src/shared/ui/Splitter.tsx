// The border between two panes, dragged to resize them — like an IDE's sash: a 1 px line (no gap
// between the panes), a wider band to grab around it, lit while hovered or dragged. While dragged,
// ``onDrag`` gets the pointer's place on screen (clientX for a border between left and right,
// clientY for one between top and bottom) and sets the sizes from it.
import { useState } from "react";
import { cn } from "@/shared/lib/cn";

export function Sash({ vertical, onDrag, label }: {
  vertical?: boolean; // between left and right (dragged sideways); else between top and bottom
  onDrag: (at: number) => void;
  label: string;
}) {
  return (
    <div className={cn("relative flex-none bg-line", vertical ? "w-px" : "h-px")}>
      <div role="separator" aria-orientation={vertical ? "vertical" : "horizontal"} aria-label={label} title={label}
           className={cn("absolute z-20 touch-none transition-colors delay-100 hover:bg-accent active:bg-accent",
                         vertical ? "inset-y-0 -left-0.75 w-1.5 cursor-col-resize" : "inset-x-0 -top-0.75 h-1.5 cursor-row-resize")}
           onPointerDown={(event) => {
             event.preventDefault();
             event.currentTarget.setPointerCapture(event.pointerId);
           }}
           onPointerMove={(event) => {
             if (event.currentTarget.hasPointerCapture(event.pointerId)) onDrag(vertical ? event.clientX : event.clientY);
           }} />
    </div>
  );
}

/** A pane's size as last dragged (this browser's, for every note; null: not dragged yet). */
export function useKeptSize(key: string): [number | null, (px: number) => void] {
  const [size, setSize] = useState<number | null>(() => {
    try { return Number(localStorage.getItem(key)) || null; } catch { return null; }
  });
  return [size, (px) => {
    setSize(px);
    try { localStorage.setItem(key, String(Math.round(px))); } catch { /* private window: this time only */ }
  }];
}
