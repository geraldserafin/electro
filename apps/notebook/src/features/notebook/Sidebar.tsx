// The note's sidebar, under the app's islands: the title, and the sections under it — a note in parts:
// the title its start (what comes before the first part), then the parts, each its sections under it.
import type { Part } from "@/shared/model/parts";
import type { Cell } from "@/shared/model/types";
import type { Spot } from "./cellList";
import { NARROW, sidebar } from "./layout";
import { Outline } from "./Outline";
import { AddPart, PartList } from "./Parts";
import { TitleBox } from "./TitleBox";

export function Sidebar({
  open,
  title,
  onTitle,
  cells,
  parts,
  page,
  editing,
  onPage,
  onMove,
  onAddPart,
  onRemove,
  onMovePart,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  onTitle: (title: string) => void;
  cells: Cell[];
  parts: Part[];
  page: number;
  editing: boolean; // its author's: the chapters to move, remove
  onPage: (page: number) => void;
  onMove: (from: Spot, until: Spot | null, before: Spot | null) => void; // a section dragged in the outline
  onAddPart: () => void; // a new chapter, at the note's end
  onRemove: (page: number) => void;
  onMovePart: (page: number, before: number) => void;
}) {
  // where it covers the note (a phone): gone once it took the reader somewhere
  const went = () => matchMedia(NARROW).matches && onClose();
  const go = (n: number) => {
    onPage(n);
    went();
  };
  const part = parts[page];
  const start = parts[0]?.name === null; // a start before the first part: the title's
  const outline = (n: number) => {
    const p = parts[n]!;
    return (
      <Outline
        cells={cells.slice(p.start, p.end)}
        skipFirst={p.name !== null} // its heading left out: it is the part's name
        current={n === page}
        onOpen={() => onPage(n)}
        onMove={(from, until, before) => {
          const end = cells[p.end] ? { cell: cells[p.end]!.id, line: 0 } : null; // the part's: the next one's start
          onMove(from, until ?? end, before ?? end);
        }}
        onGo={went}
      />
    );
  };
  if (parts.length < 2 || !part)
    return (
      <aside data-keep-focus className={sidebar(open)} inert={!open}>
        <div className="flex flex-none items-center gap-0.5 h-9 min-w-0">
          <TitleBox title={title} onChange={onTitle} />
        </div>
        <Outline cells={cells} onMove={onMove} onGo={went} />
        {editing && <AddPart onAdd={onAddPart} />}
      </aside>
    );
  return (
    <aside data-keep-focus className={sidebar(open)} inert={!open}>
      {/* the title: the start's page (its author still renames the note here) */}
      <div className="flex flex-none items-center gap-0.5 h-9 min-w-0" onClick={() => start && go(0)}>
        {editing ? (
          <TitleBox title={title} onChange={onTitle} />
        ) : (
          <button
            aria-current={start && page === 0 ? "page" : undefined}
            className="flex-1 min-w-0 h-9 px-2.5 rounded-lg text-left text-[16px] font-medium truncate hover:bg-hover"
          >
            {title}
          </button>
        )}
      </div>
      <div className="flex-1 min-h-0 overflow-y-auto overflow-x-hidden pb-2">
        {start && page === 0 && <div className="mb-1">{outline(0)}</div>}
        <PartList
          parts={start ? parts.slice(1) : parts}
          page={page}
          editing={editing}
          onPage={go}
          onRemove={onRemove}
          onMove={onMovePart}
        >
          {outline}
        </PartList>
        {editing && <AddPart onAdd={onAddPart} />}
      </div>
    </aside>
  );
}
