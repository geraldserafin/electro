// The board a schematic is drawn on, and its islands: tiles floating over it (like Excalidraw's),
// which fade in while the pointer is over the board (or something in it has the keyboard, or it is
// full screen). On touch screens (no hover) they always show. data-board: the board, for the tests.
import type { ButtonHTMLAttributes, HTMLAttributes } from "react";
import { cn } from "@/shared/lib/cn";

export const board = "group/board relative overflow-hidden rounded-xl border border-line bg-board";

const fades = "transition-opacity duration-180 [@media(hover:hover)]:opacity-0 group-hover/board:opacity-100 " +
  "group-data-full/board:opacity-100 group-has-[input:focus,textarea:focus,.cm-focused]/board:opacity-100";

/** An island's own look (also for one that is a button itself). */
export const boardIsland = (stays?: boolean) =>
  cn("absolute z-3 flex items-center gap-0.5 p-1 rounded-[10px] bg-island shadow-island", !stays && fades);

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

/** A thin line between groups of buttons. */
export const Separator = () => <span className="w-px self-stretch m-1 bg-line" />;
