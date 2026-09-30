// The table of contents: the headings of the text cells and the schematics, in order — one tile
// each, indented by level, under the title in the note's sidebar. A click scrolls there; the
// section being read is lit. Dragging a tile by its handle moves its section: the cells from its
// own to the next heading of its level or above (a heading that starts its cell; one further down
// a text is only a place to scroll to).
import { type ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { Trans, useTranslation } from "react-i18next";
import { useDragSort } from "@/shared/hooks/useDragSort";
import { cn } from "@/shared/lib/cn";
import type { Cell } from "@/shared/model/types";
import { SchematicIcon } from "@/shared/ui/icons";
import { Grip } from "./CellFrame";

type Entry = { key: string; cell: string; nth: number; level: number; text: string; schematic?: boolean };

/** "## Wyniki **R**" → level 2, "Wyniki R"; headings inside ``` blocks are code, not headings. */
function headings(cell: Cell): Entry[] {
  if (cell.type === "schematic")
    return [{ key: cell.id, cell: cell.id, nth: 0, level: 3, text: cell.name, schematic: true }];
  if (cell.type !== "markdown") return [];
  const out: Entry[] = [];
  let fenced = false;
  cell.source.split("\n").forEach((line, i) => {
    if (/^\s*(```|~~~)/.test(line)) fenced = !fenced;
    const m = !fenced && line.match(/^(#{1,3})\s+(.+?)\s*#*\s*$/);
    if (m) out.push({ key: `${cell.id}:${i}`, cell: cell.id, nth: out.length, level: m[1].length, text: plain(m[2]) });
  });
  return out;
}

/** Where an entry is on the page: its heading in the rendered text, else its cell. */
function place(e: Entry): HTMLElement | null {
  const cell = document.getElementById(`cell-${e.cell}`);
  if (!cell || e.schematic) return cell;
  const found = cell.querySelectorAll<HTMLElement>(":is(h1, h2, h3)");
  return found[e.nth] ?? cell;
}

const plain = (s: string) =>
  s
    .replace(/[*_`$]/g, "")
    .replace(/\[(.*?)\]\(.*?\)/g, "$1")
    .replace(/\\,/g, " ");

/** A section to drag: its first cell and how many. */
function section(e: Entry, entries: Entry[], cells: Cell[]): { from: number; count: number } {
  const from = cells.findIndex((c) => c.id === e.cell);
  const next = cells.findIndex((c, i) => i > from && entries.some((x) => x.cell === c.id && x.level <= e.level));
  return { from, count: (next < 0 ? cells.length : next) - from };
}

export function Outline({
  cells,
  onMove,
}: {
  cells: Cell[];
  onMove: (from: number, count: number, before: number) => void; // cells, moved before the one at before
}) {
  const { t } = useTranslation("notebook");
  const entries = useMemo(() => cells.flatMap(headings), [cells]);
  const list = useRef<HTMLUListElement>(null);
  // where a section can land: before a section-starting tile (its cell), or at the very end
  const starts = entries.filter((e) => e.nth === 0);
  const places = () => [...(list.current?.querySelectorAll<HTMLElement>("li[data-start]") ?? [])];
  const cellBefore = (before: number) =>
    before < starts.length ? cells.findIndex((c) => c.id === starts[before].cell) : cells.length;
  const [active, setActive] = useState<string | null>(null);

  // the section being read: the last entry whose cell starts above a line under the app bar
  useEffect(() => {
    const onScroll = () => {
      let current: string | null = null;
      for (const e of entries) {
        const el = place(e);
        if (el && el.getBoundingClientRect().top < 140) current = e.key;
      }
      setActive(current ?? entries[0]?.key ?? null);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [entries]);

  const top = Math.min(...entries.map((e) => e.level));
  return (
    <nav className="flex-1 min-h-0 overflow-y-auto mt-2.5 pb-2 text-[14px]" aria-label={t("outline")}>
      {entries.length === 0 && (
        <p className="mx-3 my-0 text-[13px] text-muted">
          <Trans t={t} i18nKey="outlineEmpty" components={{ code: <code /> }} />
        </p>
      )}
      <ul ref={list} className="m-0 p-0 list-none grid gap-px">
        {entries.map((e) => (
          <Row
            key={e.key}
            start={e.nth === 0}
            places={places}
            onDrop={(before) => {
              const { from, count } = section(e, entries, cells);
              onMove(from, count, cellBefore(before));
            }}
          >
            <a
              href={`#cell-${e.cell}`}
              aria-current={active === e.key ? "location" : undefined}
              className={`flex items-center gap-2 py-1.75 pr-3 rounded-lg leading-[1.35] no-underline transition-colors duration-100
                           hover:bg-selected hover:text-fg aria-[current]:bg-selected aria-[current]:text-fg aria-[current]:font-medium
                           [&>svg]:flex-none [&>svg]:size-3.75 ${e.level === top ? "text-fg font-medium" : "text-muted"}`}
              style={{ paddingLeft: 12 + (e.level - top) * 16 }}
              onClick={(event) => {
                event.preventDefault();
                place(e)?.scrollIntoView({ behavior: "smooth", block: "start" });
              }}
            >
              {e.schematic && <SchematicIcon />}
              {e.text}
            </a>
          </Row>
        ))}
      </ul>
    </nav>
  );
}

/** A tile; one that starts its cell has a handle (on hover) to drag its section by. */
function Row({
  start,
  places,
  onDrop,
  children,
}: {
  start: boolean;
  places: () => HTMLElement[];
  onDrop: (before: number) => void;
  children: ReactNode;
}) {
  const { t } = useTranslation("notebook");
  const drag = useDragSort({ items: places, onDrop });
  return (
    <li data-start={start || undefined} className={cn("group/row relative", drag.dragging && "opacity-40")}>
      {children}
      {start && (
        <button
          {...drag.handle}
          title={t("outlineDrag")}
          aria-label={t("outlineDrag")}
          tabIndex={-1}
          className="absolute right-1 top-1/2 -translate-y-1/2 inline-flex items-center justify-center size-6 rounded-md text-faint
                           cursor-grab active:cursor-grabbing touch-none opacity-0 group-hover/row:opacity-100 hover:bg-hover hover:text-fg"
        >
          <Grip />
        </button>
      )}
      {drag.line && <div className="fixed z-50 h-0.5 rounded-full bg-accent pointer-events-none" style={drag.line} />}
    </li>
  );
}
