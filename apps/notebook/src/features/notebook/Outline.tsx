// The table of contents: the headings of the text cells and the schematics, in order — one tile
// each, indented by level, under the title in the note's sidebar. A click scrolls there; the
// section being read is lit. Dragging a tile moves its section: all from its heading to the next
// one of its level or above (a text cut there into two cells, where it starts, ends or lands within one).
import { type ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { Trans, useTranslation } from "react-i18next";
import { useDragSort } from "@/shared/hooks/useDragSort";
import { cn } from "@/shared/lib/cn";
import type { Cell } from "@/shared/model/types";
import { SchematicIcon } from "@/shared/ui/icons";
import type { Spot } from "./cellList";

type Entry = {
  key: string;
  cell: string;
  line: number; // of its text: the heading's
  nth: number;
  level: number;
  text: string;
  schematic?: boolean;
};

/** "## Wyniki **R**" → level 2, "Wyniki R"; headings inside ``` blocks are code, not headings. */
function headings(cell: Cell): Entry[] {
  if (cell.type === "schematic")
    return [{ key: cell.id, cell: cell.id, line: 0, nth: 0, level: 3, text: cell.name, schematic: true }];
  if (cell.type !== "markdown") return [];
  return textHeadings(cell.id, cell.source);
}

function textHeadings(id: string, source: string): Entry[] {
  const out: Entry[] = [];
  let fenced = false;
  source.split("\n").forEach((line, i) => {
    if (/^\s*(```|~~~)/.test(line)) fenced = !fenced;
    const m = !fenced && line.match(/^(#{1,3})\s+(.+?)\s*#*\s*$/);
    if (m)
      out.push({
        key: `${id}:${i}`,
        cell: id,
        line: i,
        nth: out.length,
        level: m[1].length,
        text: plain(m[2]),
      });
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

const spot = (e: Entry | undefined): Spot | null => (e ? { cell: e.cell, line: e.line } : null);

export function Outline({
  cells,
  onMove,
  onGo,
  skipFirst,
  current = true,
  onOpen,
}: {
  cells: Cell[];
  skipFirst?: boolean; // a part's: its first heading is its name, shown above (and its cell not to be dragged)
  onMove: (from: Spot, until: Spot | null, before: Spot | null) => void; // a section (null: the cells' end)
  onGo?: () => void; // a tile was clicked: the page scrolls there
  current?: boolean; // a chapter's: the one read now (only its sections lit)
  onOpen?: () => void; // a chapter's not on the page: shown first, then scrolled to
}) {
  const { t } = useTranslation("notebook");
  const entries = useMemo(() => {
    const all = cells.flatMap(headings);
    return skipFirst && all[0]?.cell === cells[0]?.id ? all.slice(1) : all;
  }, [cells, skipFirst]);
  const list = useRef<HTMLUListElement>(null);
  // where a section can land: before a tile, or at the very end
  const places = () => [...(list.current?.querySelectorAll<HTMLElement>(":scope > li") ?? [])];
  const [active, setActive] = useState<string | null>(null);

  // the section being read: the last entry whose cell starts above a line under the app bar
  useEffect(() => {
    if (!current) return setActive(null);
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
  }, [entries, current]);

  const top = Math.min(...entries.map((e) => e.level));
  if (!entries.length && skipFirst !== undefined) return null; // a chapter with no sections
  return (
    <nav
      className={
        skipFirst === undefined
          ? "flex-1 min-h-0 overflow-y-auto overflow-x-hidden mt-2.5 pb-2 text-[14px]"
          : "py-0.5 text-[14px]"
      }
      aria-label={t("outline")}
    >
      {entries.length === 0 && skipFirst === undefined && (
        <p className="mx-3 my-0 text-[13px] text-muted">
          <Trans t={t} i18nKey="outlineEmpty" components={{ code: <code /> }} />
        </p>
      )}
      <ul ref={list} className="m-0 p-0 list-none grid gap-px">
        {entries.map((e, k) => (
          <Row
            key={e.key}
            places={places}
            onDrop={(before) =>
              onMove(spot(e)!, spot(entries.find((x, j) => j > k && x.level <= e.level)), spot(entries[before]))
            }
          >
            <a
              href={`#cell-${e.cell}`}
              draggable={false}
              aria-current={active === e.key ? "location" : undefined}
              className={`flex items-center gap-2 py-1.75 pr-3 rounded-lg leading-[1.35] no-underline transition-colors duration-100
                           hover:bg-selected hover:text-fg aria-[current]:bg-selected aria-[current]:text-fg
                           [&>svg]:flex-none [&>svg]:size-3.75 ${e.level === top && skipFirst === undefined ? "text-fg" : "text-muted"}
                           ${skipFirst === undefined ? "aria-[current]:font-medium" : ""} ${skipFirst === undefined && e.level === top ? "font-medium" : ""}`}
              style={{ paddingLeft: 12 + (e.level - top) * 16 }}
              onClick={(event) => {
                event.preventDefault();
                if (onOpen && !place(e)) {
                  onOpen();
                  setTimeout(() => place(e)?.scrollIntoView({ block: "start" }), 50);
                } else place(e)?.scrollIntoView({ behavior: "smooth", block: "start" });
                onGo?.();
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

/** A tile, dragged by itself. */
function Row({
  places,
  onDrop,
  children,
}: {
  places: () => HTMLElement[];
  onDrop: (before: number) => void;
  children: ReactNode;
}) {
  const drag = useDragSort({ items: places, onDrop, threshold: 5 });
  return (
    <li {...drag.handle} className={cn("relative select-none", drag.dragging && "opacity-40 cursor-grabbing")}>
      {children}
      {drag.line && <div className="fixed z-50 h-0.5 rounded-full bg-accent pointer-events-none" style={drag.line} />}
    </li>
  );
}
