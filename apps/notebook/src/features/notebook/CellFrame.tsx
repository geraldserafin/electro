// A cell on the page: its frame (lit while worked on), its tools on the top edge, and the add
// row on the bottom one. The cell itself (group/cell, data-focused) lights up its parts.
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import type { CellType } from "@/shared/model/types";
import { Down, Trash, Up } from "@/shared/ui/icons";
import { AddRow } from "./AddRow";

const tool = "inline-flex p-1 rounded-md border border-transparent text-muted hover:bg-hover";
const shown = "group-hover/cell:opacity-100 group-hover/cell:pointer-events-auto group-data-focused/cell:opacity-100 group-data-focused/cell:pointer-events-auto";

export function CellFrame({ id, type, focused, onFocus, onMove, onRemove, onAdd, children }: {
  id: string; type: CellType; focused: boolean; onFocus: () => void;
  onMove: (by: number) => void; onRemove: () => void; onAdd: (type: CellType) => void;
  children: ReactNode;
}) {
  const { t } = useTranslation("notebook");
  return (
    <section id={`cell-${id}`} data-cell={type} data-focused={focused || undefined}
             onFocusCapture={onFocus} onPointerDownCapture={onFocus}
             className="group/cell relative mb-3 p-2 rounded-lg border border-transparent scroll-mt-18
                        hover:border-line data-focused:border-line data-focused:shadow-raised">
      <div className={`absolute -top-3.5 right-3 z-5 flex p-0.5 rounded-lg bg-paper shadow-tools opacity-0 pointer-events-none
                       transition-opacity duration-120 ${shown}`}>
        <button className={tool} onClick={() => onMove(-1)} title={t("cell.up")} aria-label={t("cell.up")}><Up /></button>
        <button className={tool} onClick={() => onMove(1)} title={t("cell.down")} aria-label={t("cell.down")}><Down /></button>
        <button className={tool} onClick={onRemove} title={t("cell.remove")} aria-label={t("cell.remove")}><Trash /></button>
      </div>
      {children}
      <AddRow edge onAdd={onAdd} />
    </section>
  );
}
