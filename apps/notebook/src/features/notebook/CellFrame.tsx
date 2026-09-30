// A cell on the page: a block of its own (the cell draws it: a bar on top, what it holds under),
// in the margin on its right a handle to drag it elsewhere and a bin, the add row on its bottom
// edge. The frame marks it worked on (group/cell, data-focused; useCellFocused), which brings in
// its editing UI.
import { type ReactNode, useRef } from "react";
import { useTranslation } from "react-i18next";
import { useDragSort } from "@/shared/hooks/useDragSort";
import { cn } from "@/shared/lib/cn";
import type { CellType } from "@/shared/model/types";
import { Trash } from "@/shared/ui/icons";
import { AddRow } from "./AddRow";
import { barButton, CellFocusContext } from "./cells/CellBar";

export const Grip = () => (
  <svg viewBox="0 0 24 24" width={16} height={16} aria-hidden="true">
    {[7, 12, 17].flatMap((y) =>
      [9, 15].map((x) => <circle key={`${x}${y}`} cx={x} cy={y} r="1.6" fill="currentColor" />),
    )}
  </svg>
);

/** The cells on the page, in order (this one's siblings). */
const cellsOf = (el: HTMLElement | null) =>
  el?.parentElement ? [...el.parentElement.querySelectorAll<HTMLElement>(":scope > section[data-cell]")] : [];

export function CellFrame({
  id,
  type,
  focused,
  onFocus,
  onMoveTo,
  onRemove,
  onAdd,
  children,
}: {
  id: string;
  type: CellType;
  focused: boolean;
  onFocus: () => void;
  onMoveTo: (before: number) => void; // to stand before the cell now at ``before`` (their count: last)
  onRemove: () => void;
  onAdd: (type: CellType) => void;
  children: ReactNode;
}) {
  const { t } = useTranslation("notebook");
  const self = useRef<HTMLElement>(null);
  const drag = useDragSort({ items: () => cellsOf(self.current), onDrop: onMoveTo });
  const here = () => cellsOf(self.current).indexOf(self.current!);
  return (
    <section
      ref={self}
      id={`cell-${id}`}
      data-cell={type}
      data-focused={focused || undefined}
      onFocusCapture={onFocus}
      onPointerDownCapture={onFocus}
      className={cn("group/cell relative mb-4 scroll-mt-18 transition-opacity", drag.dragging && "opacity-40")}
    >
      {/* a safe strip from the block's edge, its full height: the pointer on its way to the handle or
          the bin never leaves the cell; going, they stay a moment (a slip does not take them away) */}
      <div
        className={cn(
          "absolute top-0 bottom-0 left-full z-5 flex flex-col gap-0.5 w-11 pl-2 [&_svg]:size-4",
          "invisible opacity-0 transition-[opacity,visibility] duration-150 delay-300",
          "group-hover/cell:visible group-hover/cell:opacity-100 group-hover/cell:delay-0",
          "group-data-focused/cell:visible group-data-focused/cell:opacity-100 group-data-focused/cell:delay-0",
          drag.dragging && "visible opacity-100",
          "max-[760px]:hidden",
        )}
      >
        <button
          {...drag.handle}
          className={cn(barButton, "cursor-grab active:cursor-grabbing touch-none")}
          title={t("cell.drag")}
          aria-label={t("cell.drag")}
          onKeyDown={(e) => {
            // the keyboard's way: one place up or down
            if (e.key === "ArrowUp") {
              e.preventDefault();
              onMoveTo(Math.max(0, here() - 1));
            }
            if (e.key === "ArrowDown") {
              e.preventDefault();
              onMoveTo(here() + 2);
            }
          }}
        >
          <Grip />
        </button>
        <button
          className={cn(barButton, "hover:text-danger")}
          onClick={onRemove}
          title={t("cell.remove")}
          aria-label={t("cell.remove")}
        >
          <Trash />
        </button>
      </div>
      <CellFocusContext.Provider value={focused}>{children}</CellFocusContext.Provider>
      <AddRow edge onAdd={onAdd} />
      {drag.line && <div className="fixed z-50 h-0.5 rounded-full bg-accent pointer-events-none" style={drag.line} />}
    </section>
  );
}
