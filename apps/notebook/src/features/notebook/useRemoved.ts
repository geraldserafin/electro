// Cells removed from the note (one, or a part's), to take back: Ctrl/⌘ Z brings the last ones back where they were (unless
// the keyboard is in a field, the code or a board — they undo their own), and so on back; a note
// of the last removal shows a moment, with the same "undo" on it.
import { useCallback, useEffect, useRef, useState } from "react";
import type { Cell } from "@/shared/model/types";

const SHOWN = 6000; // ms the note of a removal stays

export function useRemoved(cells: () => Cell[], setCells: (fn: (cells: Cell[]) => Cell[]) => void) {
  const stack = useRef<{ cells: Cell[]; index: number }[]>([]);
  const [last, setLast] = useState<Cell[] | null>(null); // the note shown: what was removed last
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);

  const show = (removed: Cell[] | null) => {
    clearTimeout(timer.current);
    setLast(removed);
    if (removed) timer.current = setTimeout(() => setLast(null), SHOWN);
  };

  /** ``count`` cells from the one ``id`` (a part: its cells). */
  const remove = (id: string, count = 1) => {
    const index = cells().findIndex((c) => c.id === id);
    if (index < 0) return;
    const gone = cells().slice(index, index + count);
    stack.current.push({ cells: gone, index });
    show(gone);
    setCells((all) => all.filter((c) => !gone.includes(c)));
  };

  const undo = useCallback(() => {
    const removed = stack.current.pop();
    if (!removed) return false;
    setCells((cells) => [...cells.slice(0, removed.index), ...removed.cells, ...cells.slice(removed.index)]);
    show(stack.current.at(-1)?.cells ?? null);
    return true;
  }, [setCells]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!(e.metaKey || e.ctrlKey) || e.shiftKey || e.key.toLowerCase() !== "z" || e.defaultPrevented) return;
      const target = e.target as HTMLElement | null;
      if (target?.closest("input, textarea, [contenteditable], .cm-editor, [data-board]")) return; // their own undo
      if (undo()) e.preventDefault();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [undo]);
  useEffect(() => () => clearTimeout(timer.current), []);

  return { remove, undo, last, dismiss: () => show(null) };
}
