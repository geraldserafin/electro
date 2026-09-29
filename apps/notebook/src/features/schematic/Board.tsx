// The board a schematic is drawn on, and its islands: tiles floating over it (like Excalidraw's),
// which come in (fade, slide a little) once its cell is worked on — focused, as a text cell shows
// its editor — or something in it has the keyboard, or it is full screen. Until then they do not
// take clicks. On touch screens (no hover) they always show. data-board: the board, for the tests.
import type { ButtonHTMLAttributes, HTMLAttributes } from "react";
import { cn } from "@/shared/lib/cn";

export const board = "group/board relative overflow-hidden rounded-xl border border-line bg-board";

// (written out in full: Tailwind finds its classes in the source, not in strings put together)
const fades = "transition-[opacity,translate] duration-200 ease-out " +
  "[@media(hover:hover)]:opacity-0 [@media(hover:hover)]:translate-y-1 [@media(hover:hover)]:pointer-events-none " +
  "group-data-focused/cell:opacity-100 group-data-focused/cell:translate-y-0 group-data-focused/cell:pointer-events-auto " +
  "group-data-full/board:opacity-100 group-data-full/board:translate-y-0 group-data-full/board:pointer-events-auto " +
  "group-has-[input:focus,textarea:focus,.cm-focused]/board:opacity-100 group-has-[input:focus,textarea:focus,.cm-focused]/board:translate-y-0 " +
  "group-has-[input:focus,textarea:focus,.cm-focused]/board:pointer-events-auto";

/** An island's own look (also for one that is a button itself). */
export const boardIsland = (stays?: boolean) =>
  cn("absolute z-3 flex items-center gap-0.5 p-1 rounded-[10px] bg-island shadow-panel", !stays && fades);

export function BoardIsland({ className, stays, ...props }: HTMLAttributes<HTMLDivElement> & {
  stays?: boolean; // always shown (what is wrong with the circuit)
}) {
  return (
    <div {...props}
         className={cn(boardIsland(stays), className)} />
  );
}

/** A button on an island; ``icon``: just an icon, square. One that is lit (bg-…) stays so under the pointer (hover:bg-…). */
export function BoardButton({ className, icon, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { icon?: boolean }) {
  return <button {...props} className={cn("inline-flex items-center gap-1.5 rounded-lg border border-transparent text-[15px] hover:bg-hover disabled:opacity-45", icon ? "p-1.5" : "px-2 py-1.5", className)} />;
}

/**
 * A button on an island, one size for all of them (the tools, the view switch, zoom, full screen…):
 * 40 × 36 px, so every island is 44 px tall and a column of icon islands is one width. on: chosen.
 */
export const islandButton = (on?: boolean) =>
  cn("relative flex-none min-w-10 h-9 p-0 justify-center text-fg", on && "bg-selected hover:bg-selected");

/** A thin line between groups of buttons. */
export const Separator = () => <span className="w-px self-stretch m-1 bg-line" />;
