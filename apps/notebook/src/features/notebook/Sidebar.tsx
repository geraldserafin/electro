// The note's sidebar, under the app's islands: the title, and the sections under it.
import type { Cell } from "@/shared/model/types";
import { NARROW, sidebar } from "./layout";
import { Outline } from "./Outline";
import { TitleBox } from "./TitleBox";

export function Sidebar({
  open,
  title,
  onTitle,
  cells,
  onMove,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  onTitle: (title: string) => void;
  cells: Cell[];
  onMove: (from: number, count: number, before: number) => void; // a section dragged in the outline
}) {
  return (
    <aside data-keep-focus className={sidebar(open)} inert={!open}>
      <div className="flex flex-none items-center gap-0.5 h-9 min-w-0">
        <TitleBox title={title} onChange={onTitle} />
      </div>
      {/* where it covers the note (a phone): gone once it took the reader somewhere */}
      <Outline cells={cells} onMove={onMove} onGo={() => matchMedia(NARROW).matches && onClose()} />
    </aside>
  );
}
