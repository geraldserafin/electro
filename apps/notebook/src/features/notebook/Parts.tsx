// A note in parts: under the part on its page the way to the one before and the next; in the sidebar
// the chapters, top level, each its sections under it (the one shown, or read, in bold); its author drags a
// chapter to a new place or removes it.
import { type ReactNode, useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useClickOutside } from "@/shared/hooks/useClickOutside";
import { useDragSort } from "@/shared/hooks/useDragSort";
import { cn } from "@/shared/lib/cn";
import type { Part } from "@/shared/model/parts";
import { More, Plus, Trash } from "@/shared/ui/icons";

/** Under a part: the one before and the next, by name (none for a note of one part). */
export function Pager({
  parts,
  page,
  title,
  onPage,
}: {
  parts: Part[];
  page: number;
  title: string; // the note's: the name of its start
  onPage: (page: number) => void;
}) {
  const { t } = useTranslation("notebook", { keyPrefix: "part" });
  if (parts.length < 2) return null;
  const name = (p: Part) => p.name || (p.name === null ? title : t("untitled"));
  const before = parts[page - 1];
  const next = parts[page + 1];
  const button = "grid gap-0.5 max-w-[48%] px-4 py-2.5 rounded-xl border border-line text-left hover:bg-hover";
  return (
    <nav aria-label={t("pages")} className="flex items-stretch justify-between gap-3 mt-12 pt-5 border-t border-line">
      {before ? (
        <button className={button} onClick={() => onPage(page - 1)}>
          <span className="text-[12px] text-faint">← {t("before")}</span>
          <span className="truncate text-[15px] font-medium">{name(before)}</span>
        </button>
      ) : (
        <span />
      )}
      {next && (
        <button className={cn(button, "ml-auto text-right")} onClick={() => onPage(page + 1)}>
          <span className="text-[12px] text-faint">{t("next")} →</span>
          <span className="truncate text-[15px] font-medium">{name(next)}</span>
        </button>
      )}
    </nav>
  );
}

/** The named parts, under the note's title (its start, when there is one, is the title's). */
export function PartList({
  parts,
  page,
  editing,
  onPage,
  onRemove,
  onMove,
  children,
}: {
  parts: Part[]; // the named ones, with their index among all of them
  page: number;
  editing: boolean; // its author's: the chapters to move, remove
  onPage: (page: number) => void;
  onRemove: (page: number) => void;
  onMove: (page: number, before: number) => void; // before: the index of a part (all of them: past the last)
  children: (page: number) => ReactNode; // a part's sections
}) {
  const { t } = useTranslation("notebook", { keyPrefix: "part" });
  const list = useRef<HTMLDivElement>(null);
  const first = parts.length && parts[0]!.start === 0 ? 0 : 1; // the index of the first named part
  const rows = () => [...(list.current?.querySelectorAll<HTMLElement>(":scope > [data-part]") ?? [])];
  return (
    <div ref={list} role="list" aria-label={t("pages")} className="grid grid-cols-[minmax(0,1fr)] content-start gap-px">
      {parts.map((p, k) => {
        const i = k + first;
        return (
          <Row
            key={p.start}
            rows={rows}
            editing={editing}
            onDrop={(before) => onMove(i, before + first)}
            // (only the chapter read now: its sections)
            body={i === page && <div className="ml-3 pl-1 border-l border-line empty:hidden">{children(i)}</div>}
            menu={
              <button role="menuitem" className="text-danger" onClick={() => onRemove(i)}>
                <Trash />
                {t("remove")}
              </button>
            }
          >
            <button
              onClick={() => onPage(i)}
              aria-current={i === page ? "page" : undefined}
              className={cn(
                "flex w-full items-center gap-2 py-1.75 pl-3 rounded-lg text-left text-[14px] leading-[1.35] text-muted",
                "hover:bg-hover hover:text-fg aria-[current=page]:text-fg aria-[current=page]:font-medium",
                editing ? "pr-14" : "pr-3",
              )}
            >
              <span className="flex-1 truncate">{p.name || t("untitled")}</span>
            </button>
          </Row>
        );
      })}
    </div>
  );
}

/** A part's row: its author drags it (the row itself), its ⋯ the rest (on hover). */
function Row({
  rows,
  editing,
  onDrop,
  menu,
  body,
  children,
}: {
  rows: () => HTMLElement[];
  editing: boolean;
  onDrop: (before: number) => void;
  menu: ReactNode; // its author's actions
  body: ReactNode; // under it: its sections
  children: ReactNode; // the row
}) {
  const { t } = useTranslation("notebook", { keyPrefix: "part" });
  const drag = useDragSort({ items: rows, onDrop, threshold: 5 });
  const [open, setOpen] = useState<{ top: number; left: number } | null>(null); // the menu, under its ⋯
  const ref = useRef<HTMLDivElement>(null);
  const close = useCallback(() => setOpen(null), []);
  useClickOutside(ref, !!open, close);
  useEffect(() => {
    if (!open) return;
    // over the list (fixed: the sidebar's edge does not cut it), gone once the list moves
    addEventListener("scroll", close, true);
    return () => removeEventListener("scroll", close, true);
  }, [open, close]);
  const tool =
    "inline-grid place-items-center size-6 rounded-md text-faint hover:bg-hover hover:text-fg opacity-0 group-hover/part:opacity-100 focus-visible:opacity-100";
  return (
    <div
      ref={ref}
      role="listitem"
      data-part
      className={cn("group/part grid grid-cols-[minmax(0,1fr)]", drag.dragging && "opacity-40")}
    >
      <div className="relative select-none" {...(editing ? drag.handle : {})}>
        {children}
        {editing && (
          <div className="absolute right-1 top-1 flex">
            <button
              title={t("more")}
              aria-label={t("more")}
              aria-haspopup="menu"
              aria-expanded={!!open}
              onClick={(e) => {
                const r = e.currentTarget.getBoundingClientRect();
                setOpen(open ? null : { top: r.bottom + 4, left: Math.max(8, r.right - 224) });
              }}
              className={cn(tool, open && "opacity-100 bg-hover", "pointer-coarse:opacity-100 [&>svg]:size-4")}
            >
              <More />
            </button>
          </div>
        )}
      </div>
      {open && (
        <div
          role="menu"
          onClick={close}
          style={open}
          className="fixed z-30 grid w-56 p-1 rounded-xl border border-line bg-paper shadow-menu
                         [&>button]:flex [&>button]:items-center [&>button]:gap-2.5 [&>button]:px-3 [&>button]:py-1.75 [&>button]:rounded-lg
                         [&>button]:text-[14px] [&>button]:text-left [&>button:hover]:bg-hover [&_svg]:size-4 [&_svg]:flex-none"
        >
          {menu}
        </div>
      )}
      {body}
      {drag.line && <div className="fixed z-50 h-0.5 rounded-full bg-accent pointer-events-none" style={drag.line} />}
    </div>
  );
}

/** Under the chapters, to their author: "+ Rozdział" — a new chapter, at the end. */
export function AddPart({ onAdd }: { onAdd: () => void }) {
  const { t } = useTranslation("notebook", { keyPrefix: "add" });
  return (
    <button
      className="inline-flex items-center gap-1.5 h-8 mt-1.5 px-2.5 rounded-lg text-[14px] text-muted hover:bg-hover hover:text-fg [&_svg]:size-4"
      onClick={onAdd}
    >
      <Plus /> {t("chapter")}
    </button>
  );
}
