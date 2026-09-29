// The note's sidebar, under the app's islands: the title, and the sections under it.
import type { Cell } from "@/shared/model/types";
import { sidebar } from "./layout";
import { Outline } from "./Outline";
import { TitleBox } from "./TitleBox";

export function Sidebar({ open, title, onTitle, cells, onMove }: {
  open: boolean; title: string; onTitle: (title: string) => void; cells: Cell[];
  onMove: (from: number, count: number, before: number) => void; // a section dragged in the outline
}) {
  return (
    <aside data-keep-focus className={sidebar(open)} inert={!open}>
      <div className="flex flex-none items-center gap-0.5 h-9 min-w-0">
        <TitleBox title={title} onChange={onTitle} />
      </div>
      <Outline cells={cells} onMove={onMove} />
    </aside>
  );
}
