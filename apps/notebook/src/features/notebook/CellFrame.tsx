// A cell on the page: a block of its own (the cell draws it: a bar on top, what it holds under),
// in the margin on its right a handle to drag it elsewhere and a bin, the add row on its bottom
// edge. The frame marks it worked on (group/cell, data-focused; useCellFocused), which brings in
// its editing UI.
import { useRef, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import type { CellType } from "@/shared/model/types";
import { useDragSort } from "@/shared/hooks/useDragSort";
import { cn } from "@/shared/lib/cn";
import { Trash } from "@/shared/ui/icons";
import { AddRow } from "./AddRow";
import { barButton, CellFocusContext } from "./cells/CellBar";

export const Grip = () => (
  <svg viewBox="0 0 24 24" width={16} height={16} aria-hidden="true">
    {[7, 12, 17].flatMap((y) => [9, 15].map((x) => <circle key={`${x}${y}`} cx={x} cy={y} r="1.6" fill="currentColor" />))}
  </svg>
);

/** The cells on the page, in order (this one's siblings). */
const cellsOf = (el: HTMLElement | null) =>
  el?.parentElement ? [...el.parentElement.querySelectorAll<HTMLElement>(":scope > section[data-cell]")] : [];

export function CellFrame({ id, type, focused, onFocus, onMoveTo, onRemove, onAdd, children }: {
  id: string; type: CellType; focused: boolean; onFocus: () => void;
  onMoveTo: (before: number) => void; // to stand before the cell now at ``before`` (their count: last)
  onRemove: () => void; onAdd: (type: CellType) => void;
  children: ReactNode;
}) {
  const { t } = useTranslation("notebook");
  const self = useRef<HTMLElement>(null);
  const drag = useDragSort({ items: () => cellsOf(self.current), onDrop: onMoveTo });
  const here = () => cellsOf(self.current).indexOf(self.current!);
  return (
    <section ref={self} id={`cell-${id}`} data-cell={type} data-focused={focused || undefined}
             onFocusCapture={onFocus} onPointerDownCapture={onFocus}
             className={cn("group/cell relative mb-4 scroll-mt-18 transition-opacity", drag.dragging && "opacity-40")}>
      <div className={cn("absolute top-0 -right-9 z-5 flex flex-col gap-0.5 opacity-0 pointer-events-none transition-opacity duration-120 [&_svg]:size-4",
                         "group-hover/cell:opacity-100 group-hover/cell:pointer-events-auto group-data-focused/cell:opacity-100 group-data-focused/cell:pointer-events-auto",
                         drag.dragging && "opacity-100", "max-[760px]:hidden")}>
        <button {...drag.handle} className={cn(barButton, "cursor-grab active:cursor-grabbing touch-none")}
                title={t("cell.drag")} aria-label={t("cell.drag")}
                onKeyDown={(e) => {
                  // the keyboard's way: one place up or down
                  if (e.key === "ArrowUp") { e.preventDefault(); onMoveTo(Math.max(0, here() - 1)); }
                  if (e.key === "ArrowDown") { e.preventDefault(); onMoveTo(here() + 2); }
                }}>
          <Grip />
        </button>
        <button className={cn(barButton, "hover:text-danger")} onClick={onRemove} title={t("cell.remove")} aria-label={t("cell.remove")}>
          <Trash />
        </button>
      </div>
      <CellFocusContext.Provider value={focused}>{children}</CellFocusContext.Provider>
      <AddRow edge onAdd={onAdd} />
      {drag.line && <div className="fixed z-50 h-0.5 rounded-full bg-accent pointer-events-none" style={drag.line} />}
    </section>
  );
}
