// The table of contents: a panel on the right with the headings of the text cells and the
// schematics, in order — one tile each, indented by level. A click scrolls there; the section
// being read is lit. It lies over the page (in the margin, where there is room) and slides in and
// out; folded, only its switch is left.
import { useEffect, useMemo, useState } from "react";
import { OutlineIcon, SchematicIcon } from "./icons";
import type { Cell } from "./types";

type Entry = { key: string; cell: string; nth: number; level: number; text: string; schematic?: boolean };

/** "## Wyniki **R**" → level 2, "Wyniki R"; headings inside ``` blocks are code, not headings. */
function headings(cell: Cell): Entry[] {
  if (cell.type === "schematic") return [{ key: cell.id, cell: cell.id, nth: 0, level: 3, text: cell.name, schematic: true }];
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
  const found = cell.querySelectorAll<HTMLElement>(".markdown-view:not(.print-only) :is(h1, h2, h3)");
  return found[e.nth] ?? cell;
}

const plain = (s: string) => s.replace(/[*_`$]/g, "").replace(/\[(.*?)\]\(.*?\)/g, "$1").replace(/\\,/g, " ");

export function Outline({ cells, open, onToggle }: { cells: Cell[]; open: boolean; onToggle: () => void }) {
  const entries = useMemo(() => cells.flatMap(headings), [cells]);
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
  const toggle = (
    <button className={`icon-button outline-toggle no-print ${open ? "open" : ""}`} onClick={onToggle} aria-pressed={open}
            title={open ? "Zwiń spis treści" : "Spis treści"} aria-label="Spis treści">
      <OutlineIcon />
    </button>
  );
  return (
    <>
    {toggle}
    <nav className={`outline no-print ${open ? "open" : ""}`} aria-label="Spis treści" aria-hidden={!open} inert={!open}>
      <header><h2>Spis treści</h2></header>
      {entries.length === 0 && <p className="outline-empty">Nagłówki z tekstu (<code># Tytuł</code>) i schematy pojawią się tutaj.</p>}
      <ul>
        {entries.map((e) => (
          <li key={e.key}>
            <a href={`#cell-${e.cell}`} className={`depth-${e.level - top} ${active === e.key ? "active" : ""}`}
               style={{ paddingLeft: 12 + (e.level - top) * 16 }}
               onClick={(event) => {
                 event.preventDefault();
                 place(e)?.scrollIntoView({ behavior: "smooth", block: "start" });
               }}>
              {e.schematic && <SchematicIcon />}
              {e.text}
            </a>
          </li>
        ))}
      </ul>
    </nav>
    </>
  );
}
