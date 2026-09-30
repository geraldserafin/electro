// A cell on the page: a block of its own (the cell draws it: a bar on top, what it holds under),
// in the margin on its right a handle to drag it elsewhere and a bin, the add row on its bottom
// edge (a touch screen: a + among its tools instead). The frame marks it worked on (group/cell, data-focused; useCellFocused), which brings in
// its editing UI.
import { type ReactNode, useCallback, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useClickOutside } from "@/shared/hooks/useClickOutside";
import { useDragSort } from "@/shared/hooks/useDragSort";
import { cn } from "@/shared/lib/cn";
import type { CellType } from "@/shared/model/types";
import { Plus, Trash } from "@/shared/ui/icons";
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
  // a touch screen: a cell added from its tools (under it), not from a row on its edge
  const [adding, setAdding] = useState(false);
  const add = useRef<HTMLSpanElement>(null);
  useClickOutside(
    add,
    adding,
    useCallback(() => setAdding(false), []),
  );
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
          // narrow (a phone): no room beside it — a row over its top right corner, while it is worked on
          "max-[760px]:left-auto max-[760px]:right-0 max-[760px]:-top-9 max-[760px]:bottom-auto max-[760px]:flex-row",
          "max-[760px]:w-auto max-[760px]:p-0.5 max-[760px]:rounded-lg max-[760px]:border max-[760px]:border-line max-[760px]:bg-surface",
        )}
      >
        <span ref={add} className="relative hidden pointer-coarse:inline-flex">
          <button
            className={cn(barButton, adding && "bg-selected text-fg")}
            onClick={() => setAdding(!adding)}
            title={t("add.label")}
            aria-label={t("add.label")}
            aria-haspopup="menu"
            aria-expanded={adding}
          >
            <Plus />
          </button>
          {adding && (
            <span
              role="menu"
              aria-label={t("add.label")}
              className="absolute top-full right-0 mt-1.5 z-30 grid w-40 p-1.5 rounded-xl border border-line bg-paper shadow-menu"
            >
              {(
                [
                  ["code", t("add.code")],
                  ["markdown", t("add.markdown")],
                  ["schematic", t("add.schematic")],
                ] as const
              ).map(([type, label]) => (
                <button
                  key={type}
                  role="menuitem"
                  className="flex items-center gap-2 px-3 py-2.5 rounded-lg text-left text-[15px] hover:bg-hover [&_svg]:text-muted"
                  onClick={() => {
                    setAdding(false);
                    onAdd(type);
                  }}
                >
                  <Plus />
                  {label}
                </button>
              ))}
            </span>
          )}
        </span>
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
      {/* (not on a touch screen: a finger taking up the cell under it would land on it — its tools' + instead) */}
      <AddRow edge onAdd={onAdd} />
      {drag.line && <div className="fixed z-50 h-0.5 rounded-full bg-accent pointer-events-none" style={drag.line} />}
    </section>
  );
}
