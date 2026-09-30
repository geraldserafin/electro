// A folder's picture: the box of the "New" card (a solid line, not a dashed one), with the first
// pages of up to four of its notes (the newest), small, two across. The size of a note's card, so
// the rows line up.
import type { NotePreview } from "@electro/notes-api";
import { PagePreview } from "@/features/notes";
import type { SymbolLibrary } from "@/shared/model/types";

const MINI = 88; // px: two across, in a 212 px box

export function FolderThumb({ previews, library }: { previews: readonly NotePreview[]; library: SymbolLibrary }) {
  return (
    <span
      className="grid grid-cols-2 content-start gap-2 w-53 aspect-[794/1123] mb-2 p-3 rounded-md border-[1.5px] border-faint
                     transition-[border-color] duration-120 group-hover:border-fg
                     group-focus-visible/open:outline-2 group-focus-visible/open:outline-offset-2 group-focus-visible/open:outline-accent"
    >
      {previews.slice(0, 4).map((preview, i) => (
        <span
          key={i}
          className="grid overflow-hidden rounded-[3px] bg-white shadow-island"
          style={{ width: MINI, aspectRatio: "794 / 1123" }}
        >
          <PagePreview preview={preview} library={library} width={MINI} />
        </span>
      ))}
    </span>
  );
}
